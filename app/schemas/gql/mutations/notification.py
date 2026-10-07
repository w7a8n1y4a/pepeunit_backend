import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_notification_service_gql
from app.schemas.gql.inputs.notification import (
    NotificationSettingsUpdateInput,
)
from app.schemas.gql.types.notification import (
    NotificationSettingsType,
    NotificationType,
)


@strawberry.mutation()
def mark_notification_read(
    info: Info, uuid: uuid_pkg.UUID
) -> NotificationType:
    notification_service = get_notification_service_gql(info)
    return notification_service.mapper_notification_to_notification_type(
        notification_service.mark_read(uuid)
    )


@strawberry.mutation()
def mark_all_notifications_read(info: Info) -> int:
    return get_notification_service_gql(info).mark_all_read()


@strawberry.mutation()
def update_notification_settings(
    info: Info, data: NotificationSettingsUpdateInput
) -> NotificationSettingsType:
    settings_row = get_notification_service_gql(info).update_settings(data)
    return NotificationSettingsType(**settings_row.dict())
