import asyncio
import inspect
import logging
import threading
import uuid as uuid_pkg
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

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
    OwnershipType,
)
from app.repositories.operation_task_repository import (
    OperationTaskRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.bot.utils import build_telegram_bot
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
    MAX_RESULT_LENGTH = 256

    def __init__(
        self,
        operation_task_repository: OperationTaskRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.operation_task_repository = operation_task_repository
        self.access_service = access_service

    def create(self, data: OperationTaskCreate) -> OperationTask:
        self.access_service.authorization.check_access([AgentType.USER])

        create_datetime = datetime.now(UTC)

        return self.operation_task_repository.create(
            OperationTask(
                creator_uuid=self.access_service.current_agent.uuid,
                task_type=data.task_type.value,
                create_datetime=create_datetime,
                start_datetime=create_datetime,
            )
        )

    def get(self, uuid: uuid_pkg.UUID) -> OperationTask:
        self.access_service.authorization.check_access([AgentType.USER])

        task = self.operation_task_repository.get(OperationTask(uuid=uuid))
        is_valid_object(task)

        self.access_service.authorization.check_ownership(
            task, [OwnershipType.CREATOR]
        )
        return task

    def list(
        self, filters: OperationTaskFilter | OperationTaskFilterInput
    ) -> tuple[int, list[OperationTask]]:
        self.access_service.authorization.check_access([AgentType.USER])

        filters.creator_uuid = self.access_service.current_agent.uuid

        return self.operation_task_repository.list(filters)

    def schedule(
        self,
        task: OperationTask,
        operation: OperationTaskCallable,
    ) -> None:
        task_uuid = task.uuid
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

    def is_valid_cooldown(
        self,
        task_type: OperationTaskType,
        cooldown: timedelta,
    ) -> None:
        latest_task = self.operation_task_repository.get_latest_by_type(
            task_type
        )
        if not latest_task:
            return

        delta = (
            datetime.now(UTC)
            - ensure_timezone_aware(latest_task.create_datetime)
        ).total_seconds()

        if delta <= cooldown.total_seconds():
            msg = f"Operation {task_type.value} is not available, last run was {round(delta)} s ago, but it should have taken at least {round(cooldown.total_seconds())} s"
            raise OperationTaskError(msg)

    @staticmethod
    async def _execute_background(
        task_uuid: uuid_pkg.UUID,
        operation: OperationTaskCallable,
        is_telegram_notify: bool,
    ) -> None:
        with get_hand_session() as db:
            repository = OperationTaskRepository(db)

            try:
                operation_result = operation(db)
                if inspect.isawaitable(operation_result):
                    operation_result = await operation_result
            except Exception as e:
                logging.exception(f"Failed OperationTask {task_uuid}")
                db.rollback()
                task = OperationTaskService._finish(
                    repository,
                    task_uuid,
                    OperationTaskStatus.ERROR,
                    str(e) or type(e).__name__,
                )
            else:
                task = OperationTaskService._finish(
                    repository,
                    task_uuid,
                    OperationTaskStatus.SUCCESS,
                    operation_result,
                )

            await OperationTaskService._notify_telegram(
                task, db, is_telegram_notify
            )

    @staticmethod
    def _finish(
        repository: OperationTaskRepository,
        task_uuid: uuid_pkg.UUID,
        status: OperationTaskStatus,
        result: str | None,
    ) -> OperationTask:
        task = repository.get(OperationTask(uuid=task_uuid))
        is_valid_object(task)

        task.status = status.value
        task.finish_datetime = datetime.now(UTC)
        task.result = (
            result[: OperationTaskService.MAX_RESULT_LENGTH]
            if result
            else None
        )

        return repository.update(task.uuid, task)

    @staticmethod
    async def _notify_telegram(
        task: OperationTask,
        db: Session,
        is_telegram_notify: bool,
    ) -> None:
        if not is_telegram_notify or not settings.pu_ff_telegram_bot_enable:
            return

        user = UserRepository(db).get(User(uuid=task.creator_uuid))
        if not user or not user.telegram_chat_id:
            return

        bot = build_telegram_bot()
        try:
            await bot.send_message(
                chat_id=user.telegram_chat_id,
                text=OperationTaskService._get_finish_text(task),
                parse_mode="Markdown",
            )
        except Exception as e:
            logging.error(f"Failed send OperationTask notification: {e}")
        finally:
            await bot.session.close()

    @staticmethod
    def _get_finish_text(task: OperationTask) -> str:
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
