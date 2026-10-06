import logging
import re
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

from fastapi import Depends
from pydantic import ValidationError

from app.configs.errors import LokiError, NoAccessError, NotificationError
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.dto.enum import (
    AgentType,
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
    DataPipeAlertData,
    InstanceDailyStateData,
    InstanceError,
    NotificationFilter,
    NotificationSettingsUpdate,
    UnitDailySummaryData,
    UnitErrorCount,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.notification_delivery import Delivery
from app.services.validators import is_valid_object


class NotificationService:
    SCHEDULED_LOG_WINDOW = timedelta(days=1)
    INSTANCE_ERROR_GROUPS = 3
    UNIT_SUMMARY_LIMIT = 10
    ALERT_LEVELS = [LogLevel.ERROR.value, LogLevel.CRITICAL.value]
    TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

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
        self.access_service.authorization.check_access([AgentType.USER])
        notification = self.notification_repository.get(
            Notification(uuid=uuid)
        )
        is_valid_object(notification)
        if notification.user_uuid != self.access_service.current_agent.uuid:
            msg = "Notification access not allowed"
            raise NoAccessError(msg)
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
        self.access_service.authorization.check_access([AgentType.USER])
        settings_row = self.notification_settings_repository.get_or_create(
            self.access_service.current_agent.uuid
        )
        changes = NotificationSettingsUpdate.model_validate(
            data, from_attributes=True
        ).model_dump(exclude_none=True)
        if "scheduled_notification_time" in changes:
            changes["scheduled_notification_time"] = self._validate_time(
                changes["scheduled_notification_time"]
            )
        settings_row.sqlmodel_update(changes)
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
        try:
            incoming = DataPipeAlertData.model_validate(event)
        except ValidationError:
            logging.error("Data pipe alert payload is invalid: %s", event)
            return []
        if incoming.unit_node_uuid is None:
            logging.error("Data pipe alert payload is invalid: %s", event)
            return []

        node = self._find_unit_node(incoming.unit_node_uuid)
        if node is None:
            logging.warning(
                "Data pipe alert for unknown unit node %s",
                incoming.unit_node_uuid,
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
        try:
            payload = incoming.with_node(
                unit_node_uuid=node.uuid,
                unit_uuid=node.unit_uuid,
                unit_name=None if unit is None else unit.name,
                topic_name=node.topic_name,
            )
        except ValidationError:
            logging.error("Data pipe alert rule is invalid: %s", event)
            return []
        return [
            self._create(
                user,
                settings_row,
                NotificationType.DATA_PIPE_ALERT,
                payload,
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

        if user.role == UserRole.ADMIN:
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

    def _instance_errors(self) -> list[InstanceError] | None:
        try:
            groups = self.loki_repository.query_backend_error_groups(
                self.INSTANCE_ERROR_GROUPS
            )
        except LokiError:
            logging.exception("Failed to read backend errors from Loki")
            return None
        return [
            InstanceError(count=group.count, message=group.message)
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
            InstanceDailyStateData(errors=self._instance_errors()),
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
        counts = dict.fromkeys(names, 0)
        for item in counted:
            counts[item.unit_uuid] = item.count
        rows = sorted(
            (
                UnitErrorCount(
                    unit_name=name,
                    error_count=counts[unit_uuid],
                )
                for unit_uuid, name in names.items()
            ),
            key=lambda item: item.error_count,
            reverse=True,
        )[: self.UNIT_SUMMARY_LIMIT]

        return self._create(
            user,
            settings_row,
            NotificationType.UNIT_DAILY_SUMMARY,
            UnitDailySummaryData(units=rows),
        )

    def _find_unit_node(
        self, unit_node_uuid: uuid_pkg.UUID
    ) -> UnitNode | None:
        try:
            return self.unit_node_repository.get(UnitNode(uuid=unit_node_uuid))
        except Exception:
            logging.exception("Failed to load unit node %s", unit_node_uuid)
            return None

    def _create(
        self,
        user: User,
        settings_row: NotificationSettings,
        notification_type: NotificationType,
        data: (
            InstanceDailyStateData | UnitDailySummaryData | DataPipeAlertData
        ),
    ) -> Delivery:
        notification = self.notification_repository.create(
            Notification(
                create_datetime=datetime.now(UTC),
                type=notification_type.value,
                data=data.model_dump(mode="json"),
                is_read=False,
                user_uuid=user.uuid,
            )
        )
        # push() runs after the background session closes
        self.notification_repository.db.expunge(notification)
        return Delivery(
            user_uuid=user.uuid,
            telegram_chat_id=user.telegram_chat_id,
            is_telegram_alert_enable=settings_row.is_telegram_alert_enable,
            notification=notification,
        )

    @classmethod
    def _validate_time(cls, value: str) -> str:
        if not cls.TIME_RE.fullmatch(value):
            msg = "scheduled_notification_time must be HH:MM in UTC"
            raise NotificationError(msg)
        return value
