import logging
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

from fastapi import Depends

from app import settings
from app.configs.errors import LokiError
from app.configs.redis import get_redis_session
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.dto.enum import (
    AgentType,
    LogLevel,
    NotificationType,
    OwnershipType,
    UserRole,
)
from app.repositories.loki_repository import LokiRepository
from app.repositories.notification_repository import NotificationRepository
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
    InstanceDailyStateData,
    InstanceError,
    NotificationFilter,
    NotificationIn,
    NotificationSettingsUpdate,
    UnitDailySummaryData,
    UnitErrorCount,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.notification_delivery import (
    NotificationMessage,
    notification_delivery,
)
from app.services.validators import is_valid_object


class NotificationService:
    SCHEDULED_LOG_WINDOW = timedelta(days=1)
    INSTANCE_ERROR_GROUPS = 3
    UNIT_SUMMARY_LIMIT = 10
    ALERT_LEVELS = [LogLevel.ERROR.value, LogLevel.CRITICAL.value]

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
        self.access_service.authorization.check_ownership(
            notification, [OwnershipType.CREATOR]
        )
        return notification

    def mark_read(self, uuid: uuid_pkg.UUID) -> Notification:
        self.access_service.authorization.check_access([AgentType.USER])
        notification = self.notification_repository.get(
            Notification(uuid=uuid)
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
        settings_row.sqlmodel_update(changes)
        return self.notification_settings_repository.update(
            settings_row.uuid, settings_row
        )

    def due_scheduled(
        self, now: datetime, user_uuid: uuid_pkg.UUID | None = None
    ) -> list[NotificationIn]:
        # The scheduled minute is the only gate. A later time the same day sends.
        slot_start = now.replace(second=0, microsecond=0)
        period_start = now - self.SCHEDULED_LOG_WINDOW
        recipients = self.notification_settings_repository.list_scheduled(
            now.strftime("%H:%M")
        )
        if user_uuid is not None:
            recipients = [
                item for item in recipients if item[0].uuid == user_uuid
            ]

        incoming: list[NotificationIn] = []
        for user, _settings_row in recipients:
            if user.role == UserRole.ADMIN and not (
                self.notification_repository.exists_since(
                    user.uuid,
                    NotificationType.INSTANCE_DAILY_STATE.value,
                    slot_start,
                )
            ):
                incoming.append(
                    NotificationIn(
                        type=NotificationType.INSTANCE_DAILY_STATE,
                        user_uuid=user.uuid,
                        data=InstanceDailyStateData(
                            errors=self._instance_errors()
                        ),
                    )
                )
            if self.notification_repository.exists_since(
                user.uuid,
                NotificationType.UNIT_DAILY_SUMMARY.value,
                slot_start,
            ):
                continue
            summary = self._unit_summary_data(user, period_start, now)
            if summary is None:
                continue
            incoming.append(
                NotificationIn(
                    type=NotificationType.UNIT_DAILY_SUMMARY,
                    user_uuid=user.uuid,
                    data=summary,
                )
            )
        return incoming

    async def publish_scheduled(self) -> None:
        incoming = self.due_scheduled(datetime.now(UTC))
        if not incoming:
            return
        session = get_redis_session()
        redis = await anext(session)
        try:
            for item in incoming:
                await redis.xadd(
                    notification_delivery.INCOMING_STREAM, item.stream()
                )
        finally:
            await session.aclose()

    async def notification_pipe(
        self, incoming: NotificationIn
    ) -> Notification | None:
        recipient = self.notification_settings_repository.get_recipient(
            incoming.user_uuid
        )
        if recipient is None:
            return None
        user, settings_row = recipient

        enabled = {
            NotificationType.DATA_PIPE_ALERT: (
                settings_row.is_data_pipe_alert_enable
            ),
            NotificationType.INSTANCE_DAILY_STATE: (
                settings_row.is_scheduled_alert_enable
            ),
            NotificationType.UNIT_DAILY_SUMMARY: (
                settings_row.is_scheduled_alert_enable
            ),
        }
        if not enabled[incoming.type]:
            return None

        notification = self.notification_repository.create(
            Notification(
                create_datetime=datetime.now(UTC),
                type=incoming.type.value,
                data=incoming.data.model_dump(mode="json"),
                is_read=False,
                user_uuid=user.uuid,
            )
        )
        self.notification_repository.db.expunge(notification)

        session = get_redis_session()
        redis = await anext(session)
        try:
            await redis.xadd(
                notification_delivery.stream_name(user.uuid),
                {"data": notification.model_dump_json()},
                maxlen=settings.pu_notification_stream_maxlen,
                approximate=True,
            )
        finally:
            await session.aclose()

        if settings_row.is_telegram_alert_enable:
            notification_delivery.telegram.enqueue(
                user.telegram_chat_id,
                NotificationMessage.text(notification),
            )
        return notification

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

    def _unit_summary_data(
        self,
        user: User,
        period_start: datetime,
        period_end: datetime,
    ) -> UnitDailySummaryData | None:
        _, units = self.unit_repository.list(
            UnitFilter.unlimited(creator_uuid=user.uuid)
        )
        names = {unit.uuid: unit.name for unit, _nodes in units}
        if not names:
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
        return UnitDailySummaryData(units=rows)
