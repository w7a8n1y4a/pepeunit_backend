import strawberry

from app.dto.enum import NotificationType
from app.schemas.gql.type_input_mixin import BasePaginationGql


@strawberry.input()
class NotificationFilterInput(BasePaginationGql):
    is_read: bool | None = None
    type: list[NotificationType] | None = tuple(NotificationType)


@strawberry.input()
class NotificationSettingsUpdateInput:
    is_scheduled_alert_enable: bool | None = None
    scheduled_notification_time: str | None = None
    is_data_pipe_alert_enable: bool | None = None
    is_telegram_alert_enable: bool | None = None
