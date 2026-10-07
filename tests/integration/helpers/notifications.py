import json
import uuid as uuid_pkg
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from app import settings
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.dto.enum import NotificationType, UserStatus
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.notification import (
    DataPipeAlertData,
    NotificationIn,
    NotificationSettingsUpdate,
)
from tests.integration.helpers.services import notification_service

SETTINGS_FIELDS = (
    "is_scheduled_alert_enable",
    "scheduled_notification_time",
    "is_data_pipe_alert_enable",
    "is_telegram_alert_enable",
)


def settings_update_of(
    settings_row: NotificationSettings,
) -> NotificationSettingsUpdate:
    return NotificationSettingsUpdate(
        **{field: getattr(settings_row, field) for field in SETTINGS_FIELDS}
    )


@contextmanager
def as_recipient(database, cc, user, token) -> Iterator:
    """Verified user whose notification settings are restored afterwards.

    Scheduled and data pipe alerts go to verified users only, the session
    users are verified through the telegram bot which the tests may not have.
    """
    repository = UserRepository(db=database)
    previous_status = user.status
    user.status = UserStatus.VERIFIED
    repository.update(user.uuid, user)

    service = notification_service(database, cc, token)
    saved = settings_update_of(service.get_settings())
    try:
        yield service
    finally:
        service.update_settings(saved)
        user.status = previous_status
        repository.update(user.uuid, user)


def data_pipe_alert(
    unit_node, user: User, unit_name: str | None = None, **fields
) -> NotificationIn:
    """A data pipe alert as the data pipe publishes it"""
    payload = {
        "unit_node_uuid": str(unit_node.uuid),
        "unit_uuid": str(unit_node.unit_uuid),
        "topic_name": unit_node.topic_name,
        "unit_name": unit_name,
        "value": "12.5",
        "type_value_threshold": "Max",
        "threshold_max": 10,
        **fields,
    }
    return NotificationIn(
        type=NotificationType.DATA_PIPE_ALERT,
        user_uuid=user.uuid,
        data=DataPipeAlertData.model_validate(payload),
    )


def data_pipe_stream(unit_node, user: User, **fields) -> dict[str, str]:
    """Redis fields of a data pipe alert, before they are typed"""
    payload = {
        "unit_node_uuid": str(unit_node.uuid),
        "unit_uuid": str(unit_node.unit_uuid),
        "topic_name": unit_node.topic_name,
        "value": "12.5",
        "type_value_threshold": "Max",
        "threshold_max": 10,
        **fields,
    }
    payload = {
        key: value for key, value in payload.items() if value is not None
    }
    return {
        "type": NotificationType.DATA_PIPE_ALERT.value,
        "user_uuid": str(user.uuid),
        "data": json.dumps(payload),
    }


def drop_notification(database, uuid: uuid_pkg.UUID) -> None:
    if not settings.pu_test_integration_clear_data:
        return
    with suppress(Exception):
        NotificationRepository(database).delete(Notification(uuid=uuid))


def drop_notifications(database, notifications) -> None:
    for notification in notifications:
        drop_notification(database, notification.uuid)
