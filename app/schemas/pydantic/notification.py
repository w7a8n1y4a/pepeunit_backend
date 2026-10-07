import json
import re
import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from app.configs.errors import NotificationError
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
            raise NotificationError(msg)
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
                    raise NotificationError(msg) from exc
            case _:
                msg = "filtering_values must be a json list"
                raise NotificationError(msg)

    @model_validator(mode="after")
    def check_rules(self) -> DataPipeAlertData:
        if (
            self.type_value_filtering is None
            and self.type_value_threshold is None
        ):
            msg = "type_value_filtering or type_value_threshold is required"
            raise NotificationError(msg)
        if self.type_value_filtering is not None and not self.filtering_values:
            msg = "filtering_values is required"
            raise NotificationError(msg)
        match self.type_value_threshold:
            case FilterTypeValueThreshold.MIN if self.threshold_min is None:
                msg = "threshold_min is required"
                raise NotificationError(msg)
            case FilterTypeValueThreshold.MAX if self.threshold_max is None:
                msg = "threshold_max is required"
                raise NotificationError(msg)
            case FilterTypeValueThreshold.RANGE if (
                self.threshold_min is None or self.threshold_max is None
            ):
                msg = "threshold_min and threshold_max are required"
                raise NotificationError(msg)
        return self

    @property
    def topic(self) -> str:
        return self.topic_name or str(self.unit_node_uuid or "-")


_PAYLOADS: dict[NotificationType, type[BaseModel]] = {}


class NotificationIn(BaseModel):
    """One notification already built by a producer"""

    type: NotificationType
    user_uuid: uuid_pkg.UUID
    data: InstanceDailyStateData | UnitDailySummaryData | DataPipeAlertData

    @classmethod
    def from_stream(cls, fields: dict[str, str]) -> NotificationIn:
        try:
            notification_type = NotificationType(fields["type"])
            data = _PAYLOADS[notification_type].model_validate(
                json.loads(fields["data"])
            )
        except (
            KeyError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ) as err:
            msg = "Notification payload is invalid"
            raise NotificationError(msg) from err
        return cls(
            type=notification_type,
            user_uuid=fields["user_uuid"],
            data=data,
        )

    def stream(self) -> dict[str, str]:
        return {
            "type": self.type.value,
            "user_uuid": str(self.user_uuid),
            "data": self.data.model_dump_json(),
        }


_PAYLOADS[NotificationType.INSTANCE_DAILY_STATE] = InstanceDailyStateData
_PAYLOADS[NotificationType.UNIT_DAILY_SUMMARY] = UnitDailySummaryData
_PAYLOADS[NotificationType.DATA_PIPE_ALERT] = DataPipeAlertData


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
