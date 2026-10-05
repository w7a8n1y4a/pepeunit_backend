import enum
import json
import logging
import math
import re
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

from fastapi import Depends

from app.configs.errors import LokiError, NoAccessError, NotificationError
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.dto.enum import (
    AgentType,
    FilterTypeValueFiltering,
    FilterTypeValueThreshold,
    LogLevel,
    NotificationType,
    UserRole,
)
from app.repositories.loki_repository import LokiRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.notification import (
    NotificationFilterInput,
    NotificationSettingsUpdateInput,
)
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationSettingsUpdate,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.notification_delivery import Delivery
from app.services.validators import is_valid_object, is_valid_uuid


class NotificationService:
    SCHEDULED_LOG_WINDOW = timedelta(days=1)
    INSTANCE_ERROR_GROUPS = 3
    UNIT_SUMMARY_LIMIT = 10
    ALERT_LEVELS = [LogLevel.ERROR.value, LogLevel.CRITICAL.value]
    TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    SETTINGS_FIELDS = (
        "is_scheduled_alert_enable",
        "scheduled_notification_time",
        "is_data_pipe_alert_enable",
        "is_telegram_alert_enable",
    )

    def __init__(
        self,
        notification_repository: NotificationRepository = Depends(),
        notification_settings_repository: (
            NotificationSettingsRepository
        ) = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_log_repository: UnitLogRepository = Depends(),
        loki_repository: LokiRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.notification_repository = notification_repository
        self.notification_settings_repository = (
            notification_settings_repository
        )
        self.unit_repository = unit_repository
        self.unit_node_repository = unit_node_repository
        self.unit_log_repository = unit_log_repository
        self.loki_repository = loki_repository
        self.access_service = access_service

    def list(
        self, filters: NotificationFilter | NotificationFilterInput
    ) -> tuple[int, list[Notification]]:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.notification_repository.list(
            self.access_service.current_agent.uuid, filters
        )

    def get(self, uuid: uuid_pkg.UUID) -> Notification:
        self.access_service.authorization.check_access([AgentType.USER])
        notification = self.notification_repository.get(
            Notification(uuid=uuid)
        )
        is_valid_object(notification)
        if notification.user_uuid != self.access_service.current_agent.uuid:
            msg = "Notification access not allowed"
            raise NoAccessError(msg)
        return notification

    def mark_read(self, uuid: uuid_pkg.UUID) -> Notification:
        notification = self.get(uuid)
        if notification.is_read:
            return notification

        notification.is_read = True
        notification.read_datetime = datetime.now(UTC)
        return self.notification_repository.update(
            notification.uuid, notification
        )

    def mark_all_read(self) -> int:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.notification_repository.mark_all_read(
            self.access_service.current_agent.uuid,
            datetime.now(UTC),
        )

    def get_settings(self) -> NotificationSettings:
        self.access_service.authorization.check_access([AgentType.USER])
        return self.notification_settings_repository.get_or_create(
            self.access_service.current_agent.uuid
        )

    def update_settings(
        self,
        data: (NotificationSettingsUpdateInput | NotificationSettingsUpdate),
    ) -> NotificationSettings:
        settings_row = self.get_settings()
        for field in self.SETTINGS_FIELDS:
            value = getattr(data, field)
            if value is None:
                continue
            if field == "scheduled_notification_time":
                value = self._validate_time(value)
            setattr(settings_row, field, value)
        return self.notification_settings_repository.update(
            settings_row.uuid, settings_row
        )

    def current_user_uuid(self) -> uuid_pkg.UUID:
        """The user that a notification stream belongs to"""
        self.access_service.authorization.check_access([AgentType.USER])
        return self.access_service.current_agent.uuid

    def dispatch_scheduled(self) -> list[Delivery]:
        """Stores the daily notifications that are due now.

        Backend only: the caller pushes the returned deliveries.
        """
        now = datetime.now(UTC)
        recipients = self.notification_settings_repository.list_scheduled(
            now.strftime("%H:%M")
        )
        deliveries: list[Delivery] = []
        for user, settings_row in recipients:
            try:
                deliveries.extend(
                    self._dispatch_scheduled_for_user(user, settings_row, now)
                )
            except Exception:
                logging.exception(
                    "Failed scheduled notifications for %s", user.uuid
                )
        return deliveries

    def create_data_pipe_alerts(self, event: dict) -> list[Delivery]:
        """Stores a data pipe alert for the node creator.

        Backend only: the event is a data_pipe_alerts stream message, the
        caller pushes the returned deliveries.
        """
        unit_node_uuid = event.get("unit_node_uuid")
        value = event.get("value")
        if not unit_node_uuid or value is None:
            logging.error("Data pipe alert payload is incomplete: %s", event)
            return []

        rule = self._data_pipe_rule(event)
        if rule is None:
            logging.error("Data pipe alert rule is invalid: %s", event)
            return []

        node = self._find_unit_node(str(unit_node_uuid))
        if node is None:
            logging.warning(
                "Data pipe alert for unknown unit node %s", unit_node_uuid
            )
            return []

        recipient = (
            self.notification_settings_repository.get_data_pipe_enabled(
                node.creator_uuid
            )
        )
        if recipient is None:
            return []

        user, settings_row = recipient
        unit = self.unit_repository.get(Unit(uuid=node.unit_uuid))
        payload = {
            "unit_node_uuid": str(node.uuid),
            "unit_uuid": str(node.unit_uuid),
            "unit_name": unit.name if unit else None,
            "topic_name": node.topic_name,
            "value": str(value),
            **rule,
        }
        return [
            self._create(
                user,
                settings_row,
                NotificationType.DATA_PIPE_ALERT,
                payload,
                push_sse=True,
            )
        ]

    def _dispatch_scheduled_for_user(
        self,
        user: User,
        settings_row: NotificationSettings,
        now: datetime,
    ) -> list[Delivery]:
        # The scheduled minute is the only gate. A later time the same day sends.
        slot_start = now.replace(second=0, microsecond=0)
        period_start = now - self.SCHEDULED_LOG_WINDOW
        deliveries: list[Delivery] = []

        if user.role == UserRole.ADMIN.value:
            delivery = self._dispatch_instance_state(
                user, settings_row, slot_start
            )
            if delivery:
                deliveries.append(delivery)

        _, units = self.unit_repository.list(
            UnitFilter.unlimited(creator_uuid=user.uuid)
        )
        delivery = self._dispatch_unit_summary(
            user, settings_row, units, slot_start, period_start, now
        )
        if delivery:
            deliveries.append(delivery)
        return deliveries

    def _instance_errors(self) -> list[dict] | None:
        try:
            groups = self.loki_repository.query_backend_error_groups(
                self.INSTANCE_ERROR_GROUPS
            )
        except LokiError:
            logging.exception("Failed to read backend errors from Loki")
            return None
        return [
            {"count": group.count, "message": group.message}
            for group in groups
        ]

    def _dispatch_instance_state(
        self,
        user: User,
        settings_row: NotificationSettings,
        since: datetime,
    ) -> Delivery | None:
        if self.notification_repository.exists_since(
            user.uuid,
            NotificationType.INSTANCE_DAILY_STATE.value,
            since,
        ):
            return None

        return self._create(
            user,
            settings_row,
            NotificationType.INSTANCE_DAILY_STATE,
            {"errors": self._instance_errors()},
            push_sse=False,
        )

    def _dispatch_unit_summary(
        self,
        user: User,
        settings_row: NotificationSettings,
        units: list,
        since: datetime,
        period_start: datetime,
        period_end: datetime,
    ) -> Delivery | None:
        if self.notification_repository.exists_since(
            user.uuid,
            NotificationType.UNIT_DAILY_SUMMARY.value,
            since,
        ):
            return None

        names = {unit.uuid: unit.name for unit, _nodes in units}
        if not names or not self.unit_log_repository:
            return None

        counted = self.unit_log_repository.count_errors_by_unit(
            unit_uuids=list(names),
            levels=self.ALERT_LEVELS,
            since=period_start,
            until=period_end,
            limit=self.UNIT_SUMMARY_LIMIT,
        )
        counts = {item.unit_uuid: item.count for item in counted}
        rows = sorted(
            (
                {
                    "unit_name": name,
                    "error_count": counts.get(unit_uuid, 0),
                }
                for unit_uuid, name in names.items()
            ),
            key=lambda item: item["error_count"],
            reverse=True,
        )[: self.UNIT_SUMMARY_LIMIT]

        return self._create(
            user,
            settings_row,
            NotificationType.UNIT_DAILY_SUMMARY,
            {"units": rows},
            push_sse=False,
        )

    def _find_unit_node(self, unit_node_uuid: str) -> UnitNode | None:
        try:
            return self.unit_node_repository.get(
                UnitNode(uuid=is_valid_uuid(unit_node_uuid))
            )
        except Exception:
            logging.exception("Failed to load unit node %s", unit_node_uuid)
            return None

    def _create(
        self,
        user: User,
        settings_row: NotificationSettings,
        notification_type: NotificationType,
        data: dict,
        push_sse: bool,
    ) -> Delivery:
        notification = self.notification_repository.create(
            Notification(
                create_datetime=datetime.now(UTC),
                type=notification_type.value,
                data=data,
                is_read=False,
                user_uuid=user.uuid,
            )
        )
        # deliver() runs after the background session closes
        self.notification_repository.db.expunge(notification)
        return Delivery(
            user_uuid=user.uuid,
            telegram_chat_id=user.telegram_chat_id,
            is_telegram_alert_enable=settings_row.is_telegram_alert_enable,
            notification=notification,
            push_sse=push_sse,
        )

    @staticmethod
    def _optional_float(raw: object) -> float | None:
        if raw is None:
            return None
        number = float(raw)
        if not math.isfinite(number):
            msg = "threshold must be finite"
            raise ValueError(msg)
        return number

    @staticmethod
    def _optional_enum(
        enum_type: type[enum.Enum], raw: object
    ) -> enum.Enum | None:
        return None if raw is None else enum_type(raw)

    @staticmethod
    def _filtering_values(raw: object) -> list[str | int | float] | None:
        if raw is None:
            return None
        values = json.loads(raw)
        if not isinstance(values, list) or not all(
            isinstance(item, str | int | float) for item in values
        ):
            msg = "filtering_values must be a list of strings or numbers"
            raise TypeError(msg)
        return values

    @classmethod
    def _data_pipe_rule(cls, event: dict) -> dict | None:
        """Violated rules of a data pipe alert, None when the event is malformed.

        The rules mirror the filters stage: a filtering list and/or a threshold.
        """
        try:
            type_value_filtering = cls._optional_enum(
                FilterTypeValueFiltering, event.get("type_value_filtering")
            )
            filtering_values = cls._filtering_values(
                event.get("filtering_values")
            )
            type_value_threshold = cls._optional_enum(
                FilterTypeValueThreshold, event.get("type_value_threshold")
            )
            threshold_min = cls._optional_float(event.get("threshold_min"))
            threshold_max = cls._optional_float(event.get("threshold_max"))
        except TypeError, ValueError:
            return None

        if type_value_filtering is None and type_value_threshold is None:
            return None
        if type_value_filtering is not None and not filtering_values:
            return None
        if type_value_threshold == FilterTypeValueThreshold.MIN:
            is_complete = threshold_min is not None
        elif type_value_threshold == FilterTypeValueThreshold.MAX:
            is_complete = threshold_max is not None
        elif type_value_threshold == FilterTypeValueThreshold.RANGE:
            is_complete = (
                threshold_min is not None and threshold_max is not None
            )
        else:
            is_complete = True
        if not is_complete:
            return None

        return {
            "type_value_filtering": (
                type_value_filtering.value if type_value_filtering else None
            ),
            "filtering_values": (
                filtering_values if type_value_filtering else None
            ),
            "type_value_threshold": (
                type_value_threshold.value if type_value_threshold else None
            ),
            "threshold_min": threshold_min if type_value_threshold else None,
            "threshold_max": threshold_max if type_value_threshold else None,
        }

    @classmethod
    def _validate_time(cls, value: str) -> str:
        if not cls.TIME_RE.fullmatch(value):
            msg = "scheduled_notification_time must be HH:MM in UTC"
            raise NotificationError(msg)
        return value
