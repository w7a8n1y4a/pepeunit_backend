import json
import re
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

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
    # float("nan") and float("inf") are otherwise valid floats
    model_config = ConfigDict(allow_inf_nan=False)

    value: str
    topic_name: str | None = None
    unit_node_uuid: uuid_pkg.UUID | None = None
    unit_uuid: uuid_pkg.UUID | None = None
    unit_name: str | None = None
    type_value_filtering: FilterTypeValueFiltering | None = None
    filtering_values: list[str | float] | None = None
    type_value_threshold: FilterTypeValueThreshold | None = None
    threshold_min: float | None = None
    threshold_max: float | None = None

    @field_validator("value", mode="before")
    @classmethod
    def require_value(cls, value: object) -> str:
        if value is None:
            msg = "value is required"
            raise ValueError(msg)
        return str(value)

    @field_validator("filtering_values", mode="before")
    @classmethod
    def parse_filtering_values(cls, value: object) -> object:
        # Redis sends a JSON list, the stored row already has the list
        match value:
            case None | list():
                return value
            case str():
                try:
                    return json.loads(value)
                except json.JSONDecodeError as exc:
                    msg = "filtering_values must be a json list"
                    raise ValueError(msg) from exc
            case _:
                msg = "filtering_values must be a json list"
                raise ValueError(msg)

    def with_node(
        self,
        *,
        unit_node_uuid: uuid_pkg.UUID,
        unit_uuid: uuid_pkg.UUID,
        unit_name: str | None,
        topic_name: str,
    ) -> DataPipeAlertData:
        has_filter = self.type_value_filtering is not None
        has_threshold = self.type_value_threshold is not None
        return DataPipeAlertData(
            value=self.value,
            topic_name=topic_name,
            unit_node_uuid=unit_node_uuid,
            unit_uuid=unit_uuid,
            unit_name=unit_name,
            type_value_filtering=self.type_value_filtering,
            filtering_values=self.filtering_values if has_filter else None,
            type_value_threshold=self.type_value_threshold,
            threshold_min=self.threshold_min if has_threshold else None,
            threshold_max=self.threshold_max if has_threshold else None,
        )

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
        return self.topic_name or str(self.unit_node_uuid or "-")


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
