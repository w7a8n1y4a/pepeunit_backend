import asyncio
import uuid as uuid_pkg
from collections.abc import Iterator
from contextlib import contextmanager, suppress

from app import settings
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.repositories.notification_repository import NotificationRepository
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
def as_recipient(database, cc, _user, token) -> Iterator:
    """User whose notification settings are restored afterwards."""
    service = notification_service(database, cc, token)
    saved = settings_update_of(service.get_settings())
    try:
        yield service
    finally:
        service.update_settings(saved)


def latest_notification(database, user_uuid) -> Notification | None:
    return (
        database.query(Notification)
        .filter(Notification.user_uuid == user_uuid)
        .order_by(Notification.create_datetime.desc())
        .first()
    )


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
