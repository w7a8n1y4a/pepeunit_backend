import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, field_validator, model_validator

from app.dto.enum import (
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    NotificationType,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class InstanceError(BaseModel):
    count: int
    message: str


class InstanceDailyStateData(BaseModel):
    errors: list[InstanceError] | None


class UnitErrorCount(BaseModel):
    unit_name: str
    error_count: int


class UnitDailySummaryData(BaseModel):
    units: list[UnitErrorCount]


class DataPipeAlertData(BaseModel):
    value: str
    topic_name: str | None = None
    unit_node_uuid: str | None = None
    unit_uuid: str | None = None
    unit_name: str | None = None
    type_value_filtering: FilterTypeValueFiltering | None = None
    filtering_values: list[str | float] = []
    type_value_threshold: FilterTypeValueThreshold | None = None
    threshold_min: float | None = None
    threshold_max: float | None = None

    @field_validator("filtering_values", mode="before")
    @classmethod
    def none_filtering_values(cls, value: object) -> object:
        if value is None:
            return []
        return value

    @model_validator(mode="after")
    def check_rules(self) -> DataPipeAlertData:
        if (
            self.type_value_filtering is None
            and self.type_value_threshold is None
        ):
            msg = "type_value_filtering or type_value_threshold is required"
            raise ValueError(msg)
        if self.type_value_filtering is not None and not self.filtering_values:
            msg = "filtering_values is required"
            raise ValueError(msg)
        match self.type_value_threshold:
            case FilterTypeValueThreshold.MIN if self.threshold_min is None:
                msg = "threshold_min is required"
                raise ValueError(msg)
            case FilterTypeValueThreshold.MAX if self.threshold_max is None:
                msg = "threshold_max is required"
                raise ValueError(msg)
            case FilterTypeValueThreshold.RANGE if (
                self.threshold_min is None or self.threshold_max is None
            ):
                msg = "threshold_min and threshold_max are required"
                raise ValueError(msg)
        return self

    @property
    def topic(self) -> str:
        return self.topic_name or self.unit_node_uuid or "-"


class NotificationRead(BaseModel):
    uuid: uuid_pkg.UUID
    create_datetime: datetime
    type: NotificationType
    data: dict
    is_read: bool
    read_datetime: datetime | None
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


@dataclass
class NotificationFilter(BasePaginationRestMixin):
    is_read: bool | None = None
    type: list[str] | None = Query([item.value for item in NotificationType])

    def dict(self):
        return self.__dict__
