import threading
import time

from fastapi import Depends
from sqlmodel import Session

from app.configs.restart import restart
from app.domain.instance_settings_model import InstanceSettings
from app.dto.enum import (
    AgentType,
    OperationTaskStatus,
    OperationTaskType,
    UserRole,
)
from app.repositories.instance_settings_repository import (
    InstanceSettingsRepository,
)
from app.repositories.operation_task_repository import OperationTaskRepository
from app.schemas.pydantic.instance_settings import InstanceSettingsUpdate
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.services.access_service import AccessService
from app.services.operation_task_service import OperationTaskService
from app.services.utils import merge_two_dict_first_priority
from app.services.validators import is_valid_object
from app.validators.instance_settings import is_valid_instance_settings


class InstanceSettingsService:
    def __init__(
        self,
        instance_settings_repository: InstanceSettingsRepository = Depends(),
        operation_task_service: OperationTaskService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.instance_settings_repository = instance_settings_repository
        self.operation_task_service = operation_task_service
        self.access_service = access_service

    def get(self) -> InstanceSettings:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.OWNER],
        )
        row = self.instance_settings_repository.get(
            InstanceSettings(uuid=InstanceSettings.ROW_UUID)
        )
        is_valid_object(row)
        return row

    def update(self, data: InstanceSettingsUpdate) -> InstanceSettings:
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.OWNER],
        )
        row = self.instance_settings_repository.get(
            InstanceSettings(uuid=InstanceSettings.ROW_UUID)
        )
        is_valid_object(row)
        merged = merge_two_dict_first_priority(
            data.dict(exclude_unset=True), row.dict()
        )
        validated = is_valid_instance_settings(merged)
        updated = InstanceSettings(
            uuid=row.uuid, **validated.model_dump(mode="json")
        )
        return self.instance_settings_repository.update(updated.uuid, updated)

    def reboot(self):
        self.access_service.authorization.check_access(
            [AgentType.USER],
            [UserRole.OWNER],
        )
        task = self.operation_task_service.create(
            OperationTaskCreate(task_type=OperationTaskType.REBOOT_INSTANCE)
        )
        threading.Thread(
            target=self._restart_after_response, daemon=True
        ).start()
        return task

    @staticmethod
    def mark_started(db: Session) -> None:
        task_repository = OperationTaskRepository(db)
        task = task_repository.get_latest_by_type(
            OperationTaskType.REBOOT_INSTANCE
        )
        if not task or task.status != OperationTaskStatus.RUNNING.value:
            return

        finished = OperationTaskService._finish(
            task_repository,
            task.uuid,
            OperationTaskStatus.SUCCESS,
            "Instance started",
        )
        OperationTaskService._record_alert(db, finished)

    @staticmethod
    def _restart_after_response() -> None:
        # The response leaves before the master stops every worker.
        time.sleep(1)
        restart.request()
