import asyncio
import uuid as uuid_pkg
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime

from app import settings
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.dto.enum import NotificationType, UserStatus
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.notification import NotificationSettingsUpdate
from tests.integration.helpers.services import notification_service


def settings_update_of(
    settings_row: NotificationSettings,
) -> NotificationSettingsUpdate:
    return NotificationSettingsUpdate(
        is_scheduled_alert_enable=settings_row.is_scheduled_alert_enable,
        scheduled_notification_time=settings_row.scheduled_notification_time,
        is_data_pipe_alert_enable=settings_row.is_data_pipe_alert_enable,
        is_telegram_alert_enable=settings_row.is_telegram_alert_enable,
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


def data_pipe_notification(
    unit_node, user: User, unit_name: str | None = None, **fields
) -> Notification:
    """A data pipe alert as the data pipe inserts it, still untyped."""
    data = {
        "unit_node_uuid": str(unit_node.uuid),
        "unit_uuid": str(unit_node.unit_uuid),
        "topic_name": unit_node.topic_name,
        "value": "12.5",
        "type_value_threshold": "Max",
        "threshold_max": 10,
        **fields,
    }
    if unit_name is not None:
        data["unit_name"] = unit_name
    return Notification(
        create_datetime=datetime.now(UTC),
        type=NotificationType.DATA_PIPE_ALERT.value,
        data=data,
        is_read=False,
        is_processed=False,
        user_uuid=user.uuid,
    )


def deliver_notification(service, notification: Notification) -> Notification:
    """Saves one notification and runs it through the processing job."""
    saved = service.notification_repository.bulk_create([notification])[0]
    process_saved(service, [saved])
    return service.get(saved.uuid)


def process_saved(service, notifications: list[Notification]) -> None:
    """Processes batches until these rows are closed.

    The job also picks up other unprocessed rows, so one pass is not enough
    when the table is already busy.
    """
    waiting = {item.uuid for item in notifications}
    for _ in range(10):
        if not waiting:
            return
        asyncio.run(service.process_pending())
        done = [
            uuid
            for uuid in waiting
            if service.notification_repository.get(
                Notification(uuid=uuid)
            ).is_processed
        ]
        waiting.difference_update(done)


def drop_notification(database, uuid: uuid_pkg.UUID) -> None:
    if not settings.pu_test_integration_clear_data:
        return
    with suppress(Exception):
        NotificationRepository(database).delete(Notification(uuid=uuid))


def drop_notifications(database, notifications) -> None:
    for notification in notifications:
        drop_notification(database, notification.uuid)
