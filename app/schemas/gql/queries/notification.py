import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_notification_service_gql
from app.schemas.gql.inputs.notification import NotificationFilterInput
from app.schemas.gql.types.notification import (
    NotificationSettingsType,
    NotificationsResultType,
    NotificationType,
    UnitLogAggregatesResultType,
    UnitLogAggregateType,
)


@strawberry.field()
def get_notification(info: Info, uuid: uuid_pkg.UUID) -> NotificationType:
    notification = get_notification_service_gql(info).get(uuid)
    return NotificationType(**notification.dict())


@strawberry.field()
def get_notifications(
    filters: NotificationFilterInput, info: Info
) -> NotificationsResultType:
    count, notifications = get_notification_service_gql(info).list(filters)
    return NotificationsResultType(
        count=count,
        notifications=[
            NotificationType(**notification.dict())
            for notification in notifications
        ],
    )


@strawberry.field()
def get_notification_settings(info: Info) -> NotificationSettingsType:
    settings_row = get_notification_service_gql(info).get_settings()
    return NotificationSettingsType(**settings_row.dict())


@strawberry.field()
def get_notification_unit_logs(
    info: Info, uuid: uuid_pkg.UUID
) -> UnitLogAggregatesResultType:
    logs = get_notification_service_gql(info).get_unit_log_aggregation(uuid)
    items = [UnitLogAggregateType(**item) for item in logs]
    return UnitLogAggregatesResultType(count=len(items), logs=items)
