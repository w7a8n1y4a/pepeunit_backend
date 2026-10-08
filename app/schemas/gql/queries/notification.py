import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_notification_service_gql
from app.schemas.gql.inputs.notification import NotificationFilterInput
from app.schemas.gql.types.notification import (
    NotificationSettingsType,
    NotificationsResultType,
    NotificationType,
)


@strawberry.field()
def get_notification(info: Info, uuid: uuid_pkg.UUID) -> NotificationType:
    notification_service = get_notification_service_gql(info)
    return notification_service.mapper_notification_to_notification_type(
        notification_service.get(uuid)
    )


@strawberry.field()
def get_notifications(
    filters: NotificationFilterInput, info: Info
) -> NotificationsResultType:
    notification_service = get_notification_service_gql(info)
    count, notifications = notification_service.list(filters)
    return NotificationsResultType(
        count=count,
        notifications=[
            notification_service.mapper_notification_to_notification_type(
                notification
            )
            for notification in notifications
        ],
    )


@strawberry.field()
def get_notification_settings(info: Info) -> NotificationSettingsType:
    settings_row = get_notification_service_gql(info).get_settings()
    return NotificationSettingsType(**settings_row.dict())
