import uuid as uuid_pkg
from datetime import datetime

import strawberry

from app.domain.notification_model import Notification
from app.dto.enum import NotificationType as NotificationTypeEnum
from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.schemas.pydantic.notification import notification_read


@strawberry.type(name="Notification")
class NotificationType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    create_datetime: datetime
    type: NotificationTypeEnum
    text: str | None
    is_read: bool
    read_datetime: datetime | None
    is_processed: bool
    user_uuid: uuid_pkg.UUID


def notification_type(notification: Notification) -> NotificationType:
    return NotificationType(**notification_read(notification).model_dump())


@strawberry.type()
class NotificationsResultType(TypeInputMixin):
    count: int
    notifications: list[NotificationType] = strawberry.field(
        default_factory=list
    )


@strawberry.type(name="NotificationSettings")
class NotificationSettingsType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    user_uuid: uuid_pkg.UUID
    is_scheduled_alert_enable: bool
    scheduled_notification_time: str
    is_data_pipe_alert_enable: bool
    is_telegram_alert_enable: bool
