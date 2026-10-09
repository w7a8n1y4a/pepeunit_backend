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
from app.configs.errors import CustomException, OperationTaskError
from app.domain.notification_model import Notification
from app.domain.operation_task_model import OperationTask
from app.dto.enum import (
    AgentType,
    NotificationType,
    OperationTaskStatus,
    OperationTaskType,
)
from app.repositories.notification_repository import NotificationRepository
from app.repositories.operation_task_repository import (
    OperationTaskRepository,
)
from app.schemas.pydantic.notification import OPERATION_TASK_ALERTS
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.services.access_service import AccessService
from app.services.validators import is_valid_object
from app.utils.utils import ensure_timezone_aware

OperationTaskCallable = Callable[[Session], Awaitable[str | None] | str | None]


class OperationTaskService:
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

        task = self.operation_task_repository.create(
            OperationTask(
                creator_uuid=self.access_service.current_agent.uuid,
                task_type=data.task_type.value,
                create_datetime=create_datetime,
                start_datetime=create_datetime,
            )
        )
        self._record_alert(self.operation_task_repository.db, task)
        return task

    def schedule(
        self,
        task: OperationTask,
        operation: OperationTaskCallable,
    ) -> None:
        task_uuid = task.uuid

        def runner() -> None:
            asyncio.run(self._execute_background(task_uuid, operation))

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
                    OperationTaskService._get_error_text(e),
                )
            else:
                task = OperationTaskService._finish(
                    repository,
                    task_uuid,
                    OperationTaskStatus.SUCCESS,
                    operation_result,
                )

            try:
                OperationTaskService._record_alert(db, task)
            except Exception:
                logging.exception(
                    f"Failed to record OperationTask alert {task.uuid}"
                )

    @staticmethod
    def _get_error_text(error: Exception) -> str:
        """A result keeps a raw error, http codes of it are useless here"""
        message = (
            error.raw_message
            if isinstance(error, CustomException)
            else str(error)
        )

        return message or type(error).__name__

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
        task.result = result or None

        return repository.update(task.uuid, task)

    @staticmethod
    def _record_alert(db: Session, task: OperationTask) -> None:
        if not settings.pu_ff_notification_enable:
            return

        kind = NotificationType(task.task_type)
        NotificationRepository(db).create(
            Notification(
                create_datetime=datetime.now(UTC),
                type=kind.value,
                data=OPERATION_TASK_ALERTS[kind](
                    status=task.status,
                    start_datetime=task.start_datetime,
                    finish_datetime=task.finish_datetime,
                    result=task.result,
                ).model_dump(mode="json"),
                is_read=False,
                is_processed=False,
                user_uuid=task.creator_uuid,
            )
        )
