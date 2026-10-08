import re
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, field_validator

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

    def _listed(self, values: list[str | int | float]) -> str:
        return ", ".join(
            item if isinstance(item, str) else f"{item:g}" for item in values
        )

    def _checks(self) -> list[str]:
        checks = []
        if self.type_value_threshold == FilterTypeValueThreshold.MIN:
            checks.append(f"< {self.threshold_min:g}")
        elif self.type_value_threshold == FilterTypeValueThreshold.MAX:
            checks.append(f"> {self.threshold_max:g}")
        elif self.type_value_threshold == FilterTypeValueThreshold.RANGE:
            checks.append(
                f"∉ [{self.threshold_min:g}, {self.threshold_max:g}]"
            )
        if self.type_value_filtering is not None:
            values = self._listed(self.filtering_values)
            if self.type_value_filtering == FilterTypeValueFiltering.WHITELIST:
                checks.append(f"not is {values}")
            elif (
                self.type_value_filtering == FilterTypeValueFiltering.BLACKLIST
            ):
                checks.append(f"is {values}")
        return checks

    @property
    def text(self) -> str:
        topic = self.topic_name or self.unit_node_uuid or "-"
        checks = self._checks()
        return make_monospace_table_with_title(
            [
                ["Unit", self.unit_name or "-"],
                ["Topic", topic],
                ["Value", self.value],
                ["Check", ", ".join(checks) or "-"],
            ],
            "Data pipe alert",
            lengths=[8, 40],
        )


class NotificationRead(BaseModel):
    uuid: uuid_pkg.UUID
    create_datetime: datetime
    type: NotificationType
    text: str
    is_read: bool
    read_datetime: datetime | None = None
    user_uuid: uuid_pkg.UUID


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
