import re
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.notification_model import Notification
from app.dto.enum import (
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    NotificationType,
)
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class InstanceError(BaseModel):
    count: int
    message: str


class InstanceDailyStateData(BaseModel):
    errors: list[InstanceError]

    @property
    def text(self) -> str:
        table = [
            ["Count", "Message"],
            *[[error.count, error.message or "-"] for error in self.errors],
        ]
        return make_monospace_table_with_title(
            table, "Instance daily summary", lengths=[8, 40]
        )


class UnitErrorCount(BaseModel):
    unit_name: str
    error_count: int


class UnitDailySummaryData(BaseModel):
    units: list[UnitErrorCount]

    @property
    def text(self) -> str:
        rows = [[unit.unit_name, unit.error_count] for unit in self.units] or [
            ["-", "0"]
        ]
        return make_monospace_table_with_title(
            [["Unit name", "Errors"], *rows], "Unit daily summary"
        )


class DataPipeAlertData(BaseModel):
    value: str | int | float
    topic_name: str | None = None
    unit_node_uuid: uuid_pkg.UUID | None = None
    unit_uuid: uuid_pkg.UUID | None = None
    unit_name: str | None = None
    type_value_filtering: FilterTypeValueFiltering | None = None
    filtering_values: list[str | int | float] | None = None
    type_value_threshold: FilterTypeValueThreshold | None = None
    threshold_min: float | None = None
    threshold_max: float | None = None

    @property
    def text(self) -> str:
        phrases = []
        if self.type_value_threshold == FilterTypeValueThreshold.MIN:
            phrases.append(f"is below {self.threshold_min:g}")
        elif self.type_value_threshold == FilterTypeValueThreshold.MAX:
            phrases.append(f"is above {self.threshold_max:g}")
        elif self.type_value_threshold == FilterTypeValueThreshold.RANGE:
            phrases.append(
                f"is outside [{self.threshold_min:g}, {self.threshold_max:g}]"
            )
        if self.type_value_filtering is not None:
            values = ", ".join(
                item if isinstance(item, str) else f"{item:g}"
                for item in self.filtering_values
            )
            if self.type_value_filtering == FilterTypeValueFiltering.WHITELIST:
                phrases.append(f"is not one of: {values}")
            elif (
                self.type_value_filtering == FilterTypeValueFiltering.BLACKLIST
            ):
                phrases.append(f"is one of: {values}")
        topic = self.topic_name or self.unit_node_uuid or "-"
        lines = [
            "Data pipe alert",
            f"Topic: {topic}",
            *[f"Value {self.value} {phrase}" for phrase in phrases],
        ]
        return "\n".join(lines)


def notification_text(notification_type: str, data: dict) -> str:
    model = {
        NotificationType.INSTANCE_DAILY_STATE: InstanceDailyStateData,
        NotificationType.UNIT_DAILY_SUMMARY: UnitDailySummaryData,
        NotificationType.DATA_PIPE_ALERT: DataPipeAlertData,
    }[NotificationType(notification_type)]
    return model.model_validate(data).text


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: uuid_pkg.UUID
    create_datetime: datetime
    type: NotificationType
    text: str
    is_read: bool
    read_datetime: datetime | None
    user_uuid: uuid_pkg.UUID


def notification_read(notification: Notification) -> NotificationRead:
    return NotificationRead.model_validate(notification, from_attributes=True)


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

    @field_validator("scheduled_notification_time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None or re.fullmatch(r"^([01]\d|2[0-3]):[0-5]\d$", value):
            return value
        msg = "scheduled_notification_time must be HH:MM in UTC"
        raise ValueError(msg)


@dataclass
class NotificationFilter(BasePaginationRestMixin):
    is_read: bool | None = None
    type: list[str] | None = Query([item.value for item in NotificationType])

    def dict(self):
        return self.__dict__
