import pytest

from app.domain.notification_model import Notification
from app.dto.enum import OperationTaskType
from app.schemas.pydantic.notification import NotificationSettingsUpdate
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.services.notification_service import NotificationService
from tests.integration.helpers.notifications import (
    as_recipient,
    drop_notification,
    latest_notification,
    process_saved,
)
from tests.integration.helpers.services import (
    notification_service,
    operation_task_service,
)
from tests.integration.helpers.tasks import drop_task


@pytest.fixture
def recipient_service(
    regular_user, regular_user_token, database, cc
) -> NotificationService:
    """Regular user receives data pipe alerts, settings restored afterwards"""
    with as_recipient(
        database, cc, regular_user, regular_user_token
    ) as service:
        service.update_settings(
            NotificationSettingsUpdate(is_data_pipe_alert_enable=True)
        )
        yield service


@pytest.fixture
def crud_notification(
    regular_user, regular_user_token, database, cc
) -> Notification:
    """The alert OperationTaskService writes when a task is created."""
    task = operation_task_service(database, regular_user_token).create(
        OperationTaskCreate(task_type=OperationTaskType.UPDATE_REGISTRY)
    )
    service = notification_service(database, cc, regular_user_token)
    pending = latest_notification(database, regular_user.uuid)
    process_saved(service, [pending])
    stored = service.get(pending.uuid)
    yield stored
    drop_notification(database, stored.uuid)
    drop_task(database, task.uuid)
