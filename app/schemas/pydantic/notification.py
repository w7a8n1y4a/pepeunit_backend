import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import NotificationType
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class NotificationRead(BaseModel):
    uuid: uuid_pkg.UUID
    create_datetime: datetime
    type: NotificationType
    data: dict
    is_read: bool
    read_datetime: datetime | None
    target_user_uuid: uuid_pkg.UUID


class NotificationsResult(BaseModel):
    count: int
    notifications: list[NotificationRead]


class NotificationSettingsRead(BaseModel):
    uuid: uuid_pkg.UUID
    user_uuid: uuid_pkg.UUID
    is_scheduled_alert_enable: bool
    scheduled_notification_time: str
    is_data_pipe_alert_enable: bool
    is_telegram_alert_enable: bool


class NotificationSettingsUpdate(BaseModel):
    is_scheduled_alert_enable: bool | None = None
    scheduled_notification_time: str | None = None
    is_data_pipe_alert_enable: bool | None = None
    is_telegram_alert_enable: bool | None = None


@dataclass
class NotificationFilter(BasePaginationRestMixin):
    target_user_uuid: uuid_pkg.UUID | None = None
    is_read: bool | None = None
    type: list[str] | None = Query([item.value for item in NotificationType])

    def dict(self):
        return self.__dict__
