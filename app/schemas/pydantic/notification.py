import logging
import re
import uuid as uuid_pkg
from abc import ABC, abstractmethod
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

from app.domain.notification_model import Notification
from app.dto.enum import (
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    NotificationType,
)
from app.schemas.bot.utils import make_monospace_table_with_title
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class NotificationData(BaseModel, ABC):
    """Typed notification payload. `text` is the base text, with no
    delivery wrapper.
    """

    @property
    @abstractmethod
    def text(self) -> str:
        """Base notification text."""


class InstanceError(BaseModel):
    count: int
    message: str


class InstanceDailyStateData(NotificationData):
    errors: list[InstanceError] | None

    @property
    def text(self) -> str:
        if self.errors is None:
            table = [["Loki did not return data"]]
            lengths = None
        else:
            table = [
                ["Count", "Message"],
                *[
                    [error.count, error.message or "-"]
                    for error in self.errors
                ],
            ]
            lengths = [8, 40]
        return make_monospace_table_with_title(
            table, "Instance daily summary", lengths=lengths
        )


class UnitErrorCount(BaseModel):
    unit_name: str
    error_count: int


class UnitDailySummaryData(NotificationData):
    units: list[UnitErrorCount]

    @property
    def text(self) -> str:
        if self.units:
            rows = [
                [unit.unit_name or "-", unit.error_count]
                for unit in self.units
            ]
        else:
            rows = [["-", "0"]]
        return make_monospace_table_with_title(
            [["Unit name", "Errors"], *rows], "Unit daily summary"
        )


class DataPipeAlertData(NotificationData):
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
    def filtering_values_are_a_list(cls, value: object) -> object:
        match value:
            case None | list():
                return value
            case _:
                msg = "filtering_values must be a list"
                raise ValueError(msg)

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

    @property
    def text(self) -> str:
        lines = [
            "Data pipe alert",
            f"Topic: {self.topic}",
            *[
                f"Value {self.value} {phrase}"
                for phrase in self._rule_phrases()
            ],
        ]
        return "\n".join(lines)

    def _rule_phrases(self) -> list[str]:
        phrases = []
        if self.type_value_threshold is not None:
            phrases.append(self._threshold_phrase())
        if self.type_value_filtering is not None:
            phrases.append(self._filtering_phrase())
        return phrases

    def _threshold_phrase(self) -> str:
        low = self.threshold_min
        high = self.threshold_max
        match self.type_value_threshold:
            case FilterTypeValueThreshold.MIN:
                phrase = f"is below {low:g}"
            case FilterTypeValueThreshold.MAX:
                phrase = f"is above {high:g}"
            case FilterTypeValueThreshold.RANGE:
                phrase = f"is outside [{low:g}, {high:g}]"
            case _:
                msg = f"Unknown threshold type: {self.type_value_threshold}"
                raise ValueError(msg)
        return phrase

    def _filtering_phrase(self) -> str:
        values = ", ".join(
            self._text_value(item) for item in self._filtering_list()
        )
        match self.type_value_filtering:
            case FilterTypeValueFiltering.WHITELIST:
                phrase = f"is not one of: {values}"
            case FilterTypeValueFiltering.BLACKLIST:
                phrase = f"is one of: {values}"
            case _:
                msg = f"Unknown filtering type: {self.type_value_filtering}"
                raise ValueError(msg)
        return phrase

    def _filtering_list(self) -> list[str | float]:
        if self.filtering_values is None:
            msg = "filtering_values is required"
            raise ValueError(msg)
        return self.filtering_values

    @staticmethod
    def _text_value(value: str | float | int) -> str:
        match value:
            case bool():
                rendered = str(value)
            case int() | float():
                rendered = f"{value:g}"
            case str():
                rendered = value
            case _:
                msg = f"Unexpected filtering value: {value!r}"
                raise TypeError(msg)
        return rendered


def is_notification_text(
    notification_type: str,
    data: dict,
    notification_uuid: uuid_pkg.UUID,
) -> str | None:
    """Base text of one stored notification.

    None means the row is broken. The caller still finishes the row.
    """
    payload = _notification_data(notification_type, data, notification_uuid)
    if payload is None:
        return None
    try:
        return payload.text
    except (TypeError, ValueError) as err:
        logging.error(
            f"Notification {notification_uuid} ({notification_type}) "
            f"text failed: {err}"
        )
        return None


def _notification_data(
    notification_type: str,
    data: dict,
    notification_uuid: uuid_pkg.UUID,
) -> NotificationData | None:
    try:
        match NotificationType(notification_type):
            case NotificationType.INSTANCE_DAILY_STATE:
                payload = InstanceDailyStateData.model_validate(data)
            case NotificationType.UNIT_DAILY_SUMMARY:
                payload = UnitDailySummaryData.model_validate(data)
            case NotificationType.DATA_PIPE_ALERT:
                payload = DataPipeAlertData.model_validate(data)
            case _:
                logging.error(
                    f"Notification {notification_uuid} type is not "
                    f"supported: {notification_type}"
                )
                return None
    except (ValueError, ValidationError) as err:
        logging.error(
            f"Notification {notification_uuid} ({notification_type}) "
            f"payload is invalid: {err}"
        )
        return None
    return payload


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: uuid_pkg.UUID
    create_datetime: datetime
    type: NotificationType
    text: str | None
    is_read: bool
    read_datetime: datetime | None
    is_processed: bool
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
