import logging
import re
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

from fastapi import Depends

from app.configs.errors import NoAccessError, NotificationError
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.dto.enum import AgentType, LogLevel, NotificationType, UserRole
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
from app.services.metrics_service import MetricsService
from app.services.notification_delivery import schedule_delivery
from app.services.validators import is_valid_object, is_valid_uuid

SCHEDULED_LOG_WINDOW = timedelta(days=1)
LOG_AGGREGATE_LIMIT = 50
_ALERT_LEVELS = [LogLevel.ERROR.value, LogLevel.CRITICAL.value]
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_SETTINGS_FIELDS = (
    "is_scheduled_alert_enable",
    "scheduled_notification_time",
    "is_data_pipe_alert_enable",
    "is_telegram_alert_enable",
)


class NotificationService:
    def __init__(
        self,
        notification_repository: NotificationRepository = Depends(),
        notification_settings_repository: (
            NotificationSettingsRepository
        ) = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_log_repository: UnitLogRepository = Depends(),
        metrics_service: MetricsService = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.notification_repository = notification_repository
        self.notification_settings_repository = (
            notification_settings_repository
        )
        self.unit_repository = unit_repository
        self.unit_node_repository = unit_node_repository
        self.unit_log_repository = unit_log_repository
        self.metrics_service = metrics_service
        self.access_service = access_service

    def list(
        self, filters: NotificationFilter | NotificationFilterInput
    ) -> tuple[int, list[Notification]]:
        self._check_user()
        filters.target_user_uuid = self.access_service.current_agent.uuid
        return self.notification_repository.list(filters)

    def get(self, uuid: uuid_pkg.UUID) -> Notification:
        self._check_user()
        notification = self.notification_repository.get(
            Notification(uuid=uuid)
        )
        is_valid_object(notification)
        self._check_owner(notification)
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
        self._check_user()
        return self.notification_repository.mark_all_read(
            self.access_service.current_agent.uuid,
            datetime.now(UTC),
        )

    def get_settings(self) -> NotificationSettings:
        self._check_user()
        return self.notification_settings_repository.get_or_create(
            self.access_service.current_agent.uuid
        )

    def update_settings(
        self,
        data: (NotificationSettingsUpdateInput | NotificationSettingsUpdate),
    ) -> NotificationSettings:
        settings_row = self.get_settings()
        for field in _SETTINGS_FIELDS:
            value = getattr(data, field)
            if value is None:
                continue
            if field == "scheduled_notification_time":
                value = self._validate_time(value)
            setattr(settings_row, field, value)
        return self.notification_settings_repository.update(
            settings_row.uuid, settings_row
        )

    def get_unit_log_aggregation(self, uuid: uuid_pkg.UUID) -> list[dict]:
        notification = self.get(uuid)
        if notification.type != NotificationType.UNIT_DAILY_SUMMARY.value:
            msg = "Unit log aggregation is available for a unit summary"
            raise NotificationError(msg)

        data = notification.data or {}
        unit_uuid = data.get("unit_uuid")
        period_start = data.get("period_start")
        period_end = data.get("period_end")
        if not unit_uuid or not period_start or not period_end:
            msg = "Unit summary has no log period"
            raise NotificationError(msg)

        return self._aggregate_logs(
            since=_parse_datetime(period_start),
            until=_parse_datetime(period_end),
            unit_uuid=is_valid_uuid(unit_uuid),
        )

    def dispatch_scheduled(self) -> None:
        now = datetime.now(UTC)
        recipients = self.notification_settings_repository.list_scheduled(
            now.strftime("%H:%M")
        )
        for user, settings_row in recipients:
            try:
                self._dispatch_scheduled_for_user(user, settings_row, now)
            except Exception:
                logging.exception(
                    "Failed scheduled notifications for %s", user.uuid
                )

    def create_data_pipe_alerts(self, event: dict) -> None:
        payload = self._data_pipe_payload(event)
        if payload is None:
            return

        recipients = (
            self.notification_settings_repository.list_data_pipe_enabled()
        )
        for user, settings_row in recipients:
            self._create_and_deliver(
                user,
                settings_row,
                NotificationType.DATA_PIPE_ALERT,
                payload,
            )

    def _dispatch_scheduled_for_user(
        self,
        user: User,
        settings_row: NotificationSettings,
        now: datetime,
    ) -> None:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_start = now - SCHEDULED_LOG_WINDOW

        if user.role == UserRole.ADMIN.value:
            self._dispatch_instance_state(
                user, settings_row, day_start, period_start, now
            )

        _, units = self.unit_repository.list(
            UnitFilter.unlimited(creator_uuid=user.uuid)
        )
        for unit, _nodes in units:
            self._dispatch_unit_summary(
                user, settings_row, unit, day_start, period_start, now
            )

    def _dispatch_instance_state(
        self,
        user: User,
        settings_row: NotificationSettings,
        day_start: datetime,
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        if self.notification_repository.exists_since(
            user.uuid,
            NotificationType.INSTANCE_DAILY_STATE.value,
            day_start,
        ):
            return

        metrics = self.metrics_service.get_instance_metrics(is_api=False)
        self._create_and_deliver(
            user,
            settings_row,
            NotificationType.INSTANCE_DAILY_STATE,
            {
                "entities": metrics.model_dump(),
                "errors": self._aggregate_logs(period_start, period_end),
            },
        )

    def _dispatch_unit_summary(
        self,
        user: User,
        settings_row: NotificationSettings,
        unit: Unit,
        day_start: datetime,
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        unit_uuid = str(unit.uuid)
        if self.notification_repository.exists_since(
            user.uuid,
            NotificationType.UNIT_DAILY_SUMMARY.value,
            day_start,
            unit_uuid=unit_uuid,
        ):
            return

        self._create_and_deliver(
            user,
            settings_row,
            NotificationType.UNIT_DAILY_SUMMARY,
            {
                "unit_uuid": unit_uuid,
                "unit_name": unit.name,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

    def _data_pipe_payload(self, event: dict) -> dict | None:
        unit_node_uuid = event.get("unit_node_uuid")
        unit_uuid = event.get("unit_uuid")
        value = event.get("value")
        threshold_raw = event.get("threshold_value")
        if not unit_node_uuid or value is None or threshold_raw is None:
            logging.error("Data pipe alert payload is incomplete: %s", event)
            return None
        try:
            threshold_value = float(threshold_raw)
        except (TypeError, ValueError):
            logging.error(
                "Data pipe alert threshold is invalid: %s", threshold_raw
            )
            return None

        unit_name, topic_name, resolved_unit_uuid = self._pipe_names(
            str(unit_node_uuid), str(unit_uuid) if unit_uuid else None
        )
        return {
            "unit_node_uuid": str(unit_node_uuid),
            "unit_uuid": resolved_unit_uuid,
            "unit_name": unit_name,
            "topic_name": topic_name,
            "value": str(value),
            "threshold_value": threshold_value,
        }

    def _pipe_names(
        self, unit_node_uuid: str, unit_uuid: str | None
    ) -> tuple[str | None, str | None, str | None]:
        node = self._find_unit_node(unit_node_uuid)
        if node:
            unit = self.unit_repository.get(Unit(uuid=node.unit_uuid))
            return (
                unit.name if unit else None,
                node.topic_name,
                str(node.unit_uuid),
            )

        if not unit_uuid:
            return None, None, None
        unit = self._find_unit(unit_uuid)
        if not unit:
            return None, None, unit_uuid
        return unit.name, None, str(unit.uuid)

    def _find_unit_node(self, unit_node_uuid: str) -> UnitNode | None:
        try:
            return self.unit_node_repository.get(
                UnitNode(uuid=is_valid_uuid(unit_node_uuid))
            )
        except Exception:
            logging.exception("Failed to load unit node %s", unit_node_uuid)
            return None

    def _find_unit(self, unit_uuid: str) -> Unit | None:
        try:
            return self.unit_repository.get(
                Unit(uuid=is_valid_uuid(unit_uuid))
            )
        except Exception:
            logging.exception("Failed to load unit %s", unit_uuid)
            return None

    def _aggregate_logs(
        self,
        since: datetime,
        until: datetime,
        unit_uuid: uuid_pkg.UUID | None = None,
    ) -> list[dict]:
        if not self.unit_log_repository:
            return []
        return self.unit_log_repository.aggregate(
            levels=_ALERT_LEVELS,
            since=since,
            until=until,
            unit_uuid=unit_uuid,
            limit=LOG_AGGREGATE_LIMIT,
        )

    def _create_and_deliver(
        self,
        user: User,
        settings_row: NotificationSettings,
        notification_type: NotificationType,
        data: dict,
    ) -> Notification:
        notification = self.notification_repository.create(
            Notification(
                create_datetime=datetime.now(UTC),
                type=notification_type.value,
                data=data,
                is_read=False,
                target_user_uuid=user.uuid,
            )
        )
        schedule_delivery(
            user.uuid,
            user.telegram_chat_id,
            settings_row.is_telegram_alert_enable,
            notification,
        )
        return notification

    def _check_user(self) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

    def _check_owner(self, notification: Notification) -> None:
        if (
            notification.target_user_uuid
            != self.access_service.current_agent.uuid
        ):
            msg = "Notification access not allowed"
            raise NoAccessError(msg)

    @staticmethod
    def _validate_time(value: str) -> str:
        if not _TIME_RE.fullmatch(value):
            msg = "scheduled_notification_time must be HH:MM in UTC"
            raise NotificationError(msg)
        return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
