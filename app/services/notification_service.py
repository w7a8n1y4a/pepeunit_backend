import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from operator import attrgetter

from fastapi import Depends

from app import settings
from app.configs.errors import FeatureFlagError
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.dto.enum import (
    AgentType,
    LogLevel,
    NotificationType,
    OwnershipType,
    UserRole,
    UserStatus,
)
from app.repositories.loki_repository import LokiRepository
from app.repositories.notification_repository import (
    NotificationRepository,
    PendingNotification,
)
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.gql.inputs.notification import (
    NotificationFilterInput,
    NotificationSettingsUpdateInput,
)
from app.schemas.pydantic.notification import (
    NotificationFilter,
    NotificationSettingsUpdate,
    is_notification_text,
    notification_read,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.notification_delivery import Outgoing, notification_delivery
from app.services.validators import is_valid_object


@dataclass(frozen=True)
class _UnitError:
    unit_name: str
    error_count: int


@dataclass(frozen=True)
class _Prepared:
    notification: Notification
    text: str | None
    outgoing: Outgoing | None


class NotificationService:
    SCHEDULED_LOG_WINDOW = timedelta(days=1)
    INSTANCE_ERROR_GROUPS = 3
    UNIT_SUMMARY_LIMIT = 10
    ALERT_LEVELS = [LogLevel.ERROR.value, LogLevel.CRITICAL.value]
    SCHEDULED_TYPES = (
        NotificationType.INSTANCE_DAILY_STATE.value,
        NotificationType.UNIT_DAILY_SUMMARY.value,
    )

    def __init__(
        self,
        notification_repository: NotificationRepository = Depends(),
        notification_settings_repository: (
            NotificationSettingsRepository
        ) = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_log_repository: UnitLogRepository = Depends(),
        loki_repository: LokiRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.notification_repository = notification_repository
        self.notification_settings_repository = (
            notification_settings_repository
        )
        self.unit_repository = unit_repository
        self.unit_log_repository = unit_log_repository
        self.loki_repository = loki_repository
        self.access_service = access_service

    @staticmethod
    def is_notification_enable() -> None:
        if not settings.pu_ff_notification_enable:
            raise FeatureFlagError()

    def list(
        self, filters: NotificationFilter | NotificationFilterInput
    ) -> tuple[int, list[Notification]]:
        self.is_notification_enable()
        self.access_service.authorization.check_access([AgentType.USER])
        return self.notification_repository.list(
            self.access_service.current_agent.uuid, filters, is_visible=True
        )

    def get(self, uuid: uuid_pkg.UUID) -> Notification:
        self.is_notification_enable()
        self.access_service.authorization.check_access([AgentType.USER])
        notification = self.notification_repository.get(
            Notification(uuid=uuid), is_visible=True
        )
        is_valid_object(notification)
        self.access_service.authorization.check_ownership(
            notification, [OwnershipType.CREATOR]
        )
        return notification

    def mark_read(self, uuid: uuid_pkg.UUID) -> Notification:
        self.is_notification_enable()
        self.access_service.authorization.check_access([AgentType.USER])
        notification = self.notification_repository.get(
            Notification(uuid=uuid), is_visible=True
        )
        is_valid_object(notification)
        self.access_service.authorization.check_ownership(
            notification, [OwnershipType.CREATOR]
        )
        if notification.is_read:
            return notification

        notification.is_read = True
        notification.read_datetime = datetime.now(UTC)
        return self.notification_repository.update(
            notification.uuid, notification
        )

    def mark_all_read(self) -> int:
        self.is_notification_enable()
        self.access_service.authorization.check_access([AgentType.USER])
        return self.notification_repository.mark_all_read(
            self.access_service.current_agent.uuid,
            datetime.now(UTC),
            is_visible=True,
        )

    def get_settings(self) -> NotificationSettings:
        self.is_notification_enable()
        self.access_service.authorization.check_access([AgentType.USER])
        return self.notification_settings_repository.get_or_create(
            self.access_service.current_agent.uuid
        )

    def update_settings(
        self,
        data: (NotificationSettingsUpdateInput | NotificationSettingsUpdate),
    ) -> NotificationSettings:
        self.is_notification_enable()
        self.access_service.authorization.check_access([AgentType.USER])
        settings_row = self.notification_settings_repository.get_or_create(
            self.access_service.current_agent.uuid
        )
        changes = NotificationSettingsUpdate.model_validate(
            data, from_attributes=True
        ).model_dump(exclude_none=True)
        settings_row.sqlmodel_update(changes)
        return self.notification_settings_repository.update(
            settings_row.uuid, settings_row
        )

    def save(self, notifications: list[Notification]) -> list[Notification]:
        """Stores already built notifications. Data stays an untyped dict."""
        if not settings.pu_ff_notification_enable:
            return []
        return self.notification_repository.bulk_create(notifications)

    def generate_scheduled(
        self,
        now: datetime | None = None,
        user_uuid: uuid_pkg.UUID | None = None,
    ) -> list[Notification]:
        """Writes the daily rows whose minute has come and which are not
        already stored for that minute.
        """
        if not settings.pu_ff_notification_enable:
            return []
        moment = now or datetime.now(UTC)
        recipients = self._due_recipients(moment, user_uuid)
        if not recipients:
            return []
        present = self.notification_repository.present_since(
            [user.uuid for user, _settings_row in recipients],
            self.SCHEDULED_TYPES,
            self._slot_start(moment),
        )
        rows = [
            row
            for user, _settings_row in recipients
            for row in self._scheduled_rows(user, moment, present)
        ]
        return self.notification_repository.bulk_create(rows)

    async def process_pending(self) -> int:
        """Types one locked batch, stores the text, then delivers it."""
        if not settings.pu_ff_notification_enable:
            return 0
        pending = self.notification_repository.lock_unprocessed(
            settings.pu_notification_data_pipe_alert_batch
        )
        prepared = [self._prepare(item) for item in pending]
        self.notification_repository.mark_processed(
            [(item.notification, item.text) for item in prepared]
        )
        await notification_delivery.deliver(
            [item.outgoing for item in prepared if item.outgoing is not None]
        )
        return len(prepared)

    def _due_recipients(
        self, moment: datetime, user_uuid: uuid_pkg.UUID | None
    ) -> list[tuple[User, NotificationSettings]]:
        recipients = self.notification_settings_repository.list_scheduled(
            moment.strftime("%H:%M")
        )
        if user_uuid is None:
            return recipients
        return [
            (user, settings_row)
            for user, settings_row in recipients
            if user.uuid == user_uuid
        ]

    def _scheduled_rows(
        self,
        user: User,
        moment: datetime,
        present: set[tuple[uuid_pkg.UUID, str]],
    ) -> list[Notification]:
        rows = []
        if self._needs_instance_state(user, present):
            rows.append(self._instance_state(user))
        summary = self._unit_summary(user, moment, present)
        if summary is not None:
            rows.append(summary)
        return rows

    def _needs_instance_state(
        self, user: User, present: set[tuple[uuid_pkg.UUID, str]]
    ) -> bool:
        key = (user.uuid, NotificationType.INSTANCE_DAILY_STATE.value)
        return user.role == UserRole.ADMIN and key not in present

    def _instance_state(self, user: User) -> Notification:
        return self._new(
            user,
            NotificationType.INSTANCE_DAILY_STATE,
            self._instance_data(),
        )

    def _instance_data(self) -> dict:
        groups = self.loki_repository.backend_error_groups(
            self.INSTANCE_ERROR_GROUPS
        )
        if groups is None:
            return {"errors": None}
        return {
            "errors": [
                {"count": group.count, "message": group.message}
                for group in groups
            ]
        }

    def _unit_summary(
        self,
        user: User,
        moment: datetime,
        present: set[tuple[uuid_pkg.UUID, str]],
    ) -> Notification | None:
        key = (user.uuid, NotificationType.UNIT_DAILY_SUMMARY.value)
        if key in present:
            return None
        data = self._unit_summary_data(user, moment)
        if data is None:
            return None
        return self._new(user, NotificationType.UNIT_DAILY_SUMMARY, data)

    def _unit_summary_data(self, user: User, moment: datetime) -> dict | None:
        _, units = self.unit_repository.list(
            UnitFilter.unlimited(creator_uuid=user.uuid)
        )
        names = {unit.uuid: unit.name for unit, _nodes in units}
        if not names:
            return None
        counted = self.unit_log_repository.count_errors_by_unit(
            unit_uuids=list(names),
            levels=self.ALERT_LEVELS,
            since=moment - self.SCHEDULED_LOG_WINDOW,
            until=moment,
            limit=len(names),
        )
        counts = {item.unit_uuid: item.count for item in counted}
        ranked = sorted(
            (
                _UnitError(
                    unit_name=name,
                    error_count=self._error_count(counts, unit_uuid),
                )
                for unit_uuid, name in names.items()
            ),
            key=attrgetter("error_count"),
            reverse=True,
        )[: self.UNIT_SUMMARY_LIMIT]
        return {
            "units": [
                {
                    "unit_name": item.unit_name,
                    "error_count": item.error_count,
                }
                for item in ranked
            ]
        }

    def _prepare(self, pending: PendingNotification) -> _Prepared:
        notification = pending.notification
        text = is_notification_text(
            notification.type, notification.data, notification.uuid
        )
        if text is None:
            return _Prepared(notification, None, None)
        return _Prepared(notification, text, self._outgoing(pending, text))

    def _outgoing(
        self, pending: PendingNotification, text: str
    ) -> Outgoing | None:
        if not self._is_deliverable(pending):
            return None
        notification = pending.notification
        notification.text = text
        read = notification_read(notification)
        return Outgoing(
            user_uuid=pending.user.uuid,
            chat_id=pending.user.telegram_chat_id,
            telegram=pending.settings.is_telegram_alert_enable,
            notification_type=NotificationType(notification.type),
            text=text,
            sse_body=read.model_dump_json(),
        )

    def _is_deliverable(self, pending: PendingNotification) -> bool:
        if pending.user.status != UserStatus.VERIFIED.value:
            return False
        return self._is_type_enabled(
            pending.notification.type, pending.settings
        )

    @staticmethod
    def _new(
        user: User, notification_type: NotificationType, data: dict
    ) -> Notification:
        return Notification(
            create_datetime=datetime.now(UTC),
            type=notification_type.value,
            data=data,
            is_read=False,
            is_processed=False,
            user_uuid=user.uuid,
        )

    @staticmethod
    def _slot_start(moment: datetime) -> datetime:
        return moment.replace(second=0, microsecond=0)

    @staticmethod
    def _error_count(
        counts: dict[uuid_pkg.UUID, int], unit_uuid: uuid_pkg.UUID
    ) -> int:
        if unit_uuid in counts:
            return counts[unit_uuid]
        return 0

    @staticmethod
    def _is_type_enabled(
        notification_type: str, settings_row: NotificationSettings
    ) -> bool:
        match NotificationType(notification_type):
            case NotificationType.DATA_PIPE_ALERT:
                enabled = settings_row.is_data_pipe_alert_enable
            case (
                NotificationType.INSTANCE_DAILY_STATE
                | NotificationType.UNIT_DAILY_SUMMARY
            ):
                enabled = settings_row.is_scheduled_alert_enable
            case _:
                enabled = False
        return enabled
