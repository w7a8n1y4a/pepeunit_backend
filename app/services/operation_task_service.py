import asyncio
import inspect
import logging
import threading
import uuid as uuid_pkg
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import Depends
from sqlmodel import Session

from app import settings
from app.configs.db import get_hand_session
from app.configs.errors import OperationTaskError
from app.domain.operation_task_model import OperationTask
from app.domain.user_model import User
from app.dto.enum import (
    AgentType,
    OperationTaskStatus,
    OperationTaskType,
)
from app.repositories.operation_task_repository import (
    OperationTaskRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.gql.inputs.operation_task import OperationTaskFilterInput
from app.schemas.pydantic.operation_task import (
    OperationTaskCreate,
    OperationTaskFilter,
)
from app.services.access_service import AccessService
from app.services.validators import is_valid_object
from app.utils.utils import ensure_timezone_aware

OperationTaskCallable = Callable[[Session], Awaitable[str | None] | str | None]


class OperationTaskService:
    _MAX_OPERATION_TASK_RESULT_LENGTH = 256

    def __init__(
        self,
        operation_task_repository: OperationTaskRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.operation_task_repository = operation_task_repository
        self.access_service = access_service

    def create(self, data: OperationTaskCreate) -> OperationTask:
        self.access_service.authorization.check_access([AgentType.USER])
        now = datetime.now(UTC)
        task = OperationTask(
            creator_uuid=self.access_service.current_agent.uuid,
            task_type=data.task_type.value,
            create_datetime=now,
            start_datetime=now,
        )
        return self.operation_task_repository.create(task)

    def ensure_cooldown(
        self,
        task_type: OperationTaskType,
        cooldown: timedelta,
    ) -> str | None:
        latest = self.operation_task_repository.get_latest_by_type(task_type)
        if (
            latest is not None
            and ensure_timezone_aware(latest.create_datetime)
            > datetime.now(UTC) - cooldown
        ):
            return (
                f"Operation {task_type.value} may only run once per "
                f"{int(cooldown.total_seconds())} seconds"
            )
        return None

    def get(self, task_uuid: uuid_pkg.UUID) -> OperationTask:
        return self._get_current_user_task(task_uuid)

    def list(
        self,
        filters: OperationTaskFilter | OperationTaskFilterInput,
    ) -> tuple[int, list[OperationTask]]:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.operation_task_repository.list_for_user(
            self.access_service.current_agent.uuid,
            filters,
        )

    def schedule(
        self,
        task_uuid: uuid_pkg.UUID,
        operation: OperationTaskCallable,
    ) -> None:
        task = self._get_current_user_task(task_uuid)
        self._ensure_status(task, OperationTaskStatus.RUNNING)
        is_telegram_notify = self.access_service.is_bot_auth

        def runner() -> None:
            asyncio.run(
                self._execute_background(
                    task_uuid,
                    operation,
                    is_telegram_notify,
                )
            )

        threading.Thread(target=runner, daemon=True).start()

    @staticmethod
    async def _execute_background(
        task_uuid: uuid_pkg.UUID,
        operation: OperationTaskCallable,
        is_telegram_notify: bool,
    ) -> None:
        with get_hand_session() as db:
            repository = OperationTaskRepository(db)
            task = repository.get(OperationTask(uuid=task_uuid))
            is_valid_object(task)
            OperationTaskService._ensure_status(
                task,
                OperationTaskStatus.RUNNING,
            )

            try:
                operation_result = operation(db)
                if inspect.isawaitable(operation_result):
                    operation_result = await operation_result
            except Exception as operation_error:
                logging.exception(
                    "Operation task %s failed",
                    task_uuid,
                )
                db.rollback()
                task = repository.get(OperationTask(uuid=task_uuid))
                is_valid_object(task)
                result_text = (
                    str(operation_error) or type(operation_error).__name__
                )
                task = OperationTaskService._error_with_repository(
                    task,
                    result_text,
                    repository,
                )
                await OperationTaskService._notify_telegram(
                    task,
                    db,
                    is_telegram_notify,
                )
                return

            task = repository.get(OperationTask(uuid=task_uuid))
            is_valid_object(task)
            task = OperationTaskService._success_with_repository(
                task,
                repository,
                operation_result,
            )
            await OperationTaskService._notify_telegram(
                task,
                db,
                is_telegram_notify,
            )

    def _get_current_user_task(
        self,
        task_uuid: uuid_pkg.UUID,
    ) -> OperationTask:
        self.access_service.authorization.check_access([AgentType.USER])
        task = self.operation_task_repository.get_for_user(
            task_uuid,
            self.access_service.current_agent.uuid,
        )
        is_valid_object(task)
        return task

    @staticmethod
    def _ensure_status(
        task: OperationTask,
        expected_status: OperationTaskStatus,
    ) -> None:
        if task.status != expected_status.value:
            message = (
                f"Operation task must have status {expected_status.value}; "
                f"current status is {task.status}"
            )
            raise OperationTaskError(message)

    @staticmethod
    def _success_with_repository(
        task: OperationTask,
        repository: OperationTaskRepository,
        result_text: str | None,
    ) -> OperationTask:
        OperationTaskService._ensure_status(
            task,
            OperationTaskStatus.RUNNING,
        )
        task.status = OperationTaskStatus.SUCCESS.value
        task.finish_datetime = datetime.now(UTC)
        task.result = OperationTaskService._clip_result(result_text)
        return repository.update(task.uuid, task)

    @staticmethod
    def _error_with_repository(
        task: OperationTask,
        result_text: str,
        repository: OperationTaskRepository,
    ) -> OperationTask:
        OperationTaskService._ensure_status(
            task,
            OperationTaskStatus.RUNNING,
        )
        task.status = OperationTaskStatus.ERROR.value
        task.finish_datetime = datetime.now(UTC)
        task.result = OperationTaskService._clip_result(result_text)
        return repository.update(task.uuid, task)

    @staticmethod
    def _clip_result(result_text: str | None) -> str | None:
        if result_text is None:
            return None
        return result_text[
            : OperationTaskService._MAX_OPERATION_TASK_RESULT_LENGTH
        ]

    @staticmethod
    async def _notify_telegram(
        task: OperationTask,
        db: Session,
        is_telegram_notify: bool,
    ) -> None:
        if not is_telegram_notify:
            return
        if not settings.pu_ff_telegram_bot_enable:
            return

        user = UserRepository(db).get(User(uuid=task.creator_uuid))
        if user is None or user.telegram_chat_id is None:
            return

        session = (
            AiohttpSession(proxy=settings.pu_telegram_proxy_url)
            if settings.pu_telegram_proxy_url
            else None
        )
        bot = (
            Bot(token=settings.pu_telegram_token, session=session)
            if session is not None
            else Bot(token=settings.pu_telegram_token)
        )
        try:
            await bot.send_message(
                chat_id=user.telegram_chat_id,
                text=OperationTaskService._telegram_finish_text(task),
                parse_mode="Markdown",
            )
        except Exception as notify_error:
            logging.error(
                f"Failed to send telegram task notification: {notify_error}"
            )
        finally:
            await bot.session.close()

    @staticmethod
    def _telegram_finish_text(task: OperationTask) -> str:
        result_line = ""
        if task.result:
            escaped_result = task.result.replace("`", "'")
            result_line = f"\nResult: `{escaped_result}`"
        return (
            f"*Task finished*\n"
            f"Type: `{task.task_type}`\n"
            f"Status: `{task.status}`"
            f"{result_line}"
        )
