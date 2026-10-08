import logging
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta
from operator import attrgetter

from fastapi import Depends

from app import settings
from app.configs.errors import FeatureFlagError
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.dto.enum import (
    AgentType,
    LogLevel,
    NotificationType,
    OwnershipType,
    UserRole,
    UserStatus,
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
from app.schemas.gql.types.notification import (
    NotificationType as NotificationTypeGql,
)
from app.schemas.pydantic.notification import (
    DataPipeAlertData,
    InstanceDailyStateData,
    InstanceError,
    NotificationFilter,
    NotificationRead,
    NotificationSettingsUpdate,
    UnitDailySummaryData,
    UnitErrorCount,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.access_service import AccessService
from app.services.notification_delivery import (
    NotificationDelivery,
    notification_delivery,
)
from app.services.validators import is_valid_object


class NotificationService:
    SCHEDULED_LOG_WINDOW = timedelta(days=1)
    INSTANCE_ERROR_GROUPS = 3
    UNIT_SUMMARY_LIMIT = 10
    ALERT_LEVELS = [LogLevel.ERROR.value, LogLevel.CRITICAL.value]
    SCHEDULED_TYPES = (
        NotificationType.INSTANCE_DAILY_STATE.value,
        NotificationType.UNIT_DAILY_SUMMARY.value,
    )
    PAYLOADS = {
        NotificationType.INSTANCE_DAILY_STATE: InstanceDailyStateData,
        NotificationType.UNIT_DAILY_SUMMARY: UnitDailySummaryData,
        NotificationType.DATA_PIPE_ALERT: DataPipeAlertData,
    }

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

    @staticmethod
    def mapper_notification_to_notification_type(
        notification: Notification,
    ) -> NotificationTypeGql:
        notification_dict = notification.dict()
        del notification_dict["data"]
        del notification_dict["is_processed"]
        return NotificationTypeGql(**notification_dict)

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
        self.is_notification_enable()
        return self.notification_repository.bulk_create(notifications)

    def generate_scheduled(
        self,
        now: datetime | None = None,
        user_uuid: uuid_pkg.UUID | None = None,
    ) -> list[Notification]:
        self.is_notification_enable()
        moment = now or datetime.now(UTC)
        recipients = self.notification_settings_repository.list_scheduled(
            moment.strftime("%H:%M")
        )
        if user_uuid is not None:
            recipients = [
                (user, settings_row)
                for user, settings_row in recipients
                if user.uuid == user_uuid
            ]
        if not recipients:
            return []

        present = self.notification_repository.present_since(
            [user.uuid for user, _settings_row in recipients],
            self.SCHEDULED_TYPES,
            moment.replace(second=0, microsecond=0),
        )
        rows = []
        for user, _settings_row in recipients:
            instance_key = (
                user.uuid,
                NotificationType.INSTANCE_DAILY_STATE.value,
            )
            if user.role == UserRole.ADMIN and instance_key not in present:
                groups = self.loki_repository.backend_error_groups(
                    self.INSTANCE_ERROR_GROUPS
                )
                rows.append(
                    Notification(
                        create_datetime=datetime.now(UTC),
                        type=NotificationType.INSTANCE_DAILY_STATE.value,
                        data=InstanceDailyStateData(
                            errors=[
                                InstanceError(
                                    count=group.count,
                                    message=group.message,
                                )
                                for group in groups
                            ]
                        ).model_dump(),
                        is_read=False,
                        is_processed=False,
                        user_uuid=user.uuid,
                    )
                )

            summary_key = (
                user.uuid,
                NotificationType.UNIT_DAILY_SUMMARY.value,
            )
            if summary_key in present:
                continue
            _, units = self.unit_repository.list(
                UnitFilter.unlimited(creator_uuid=user.uuid)
            )
            names = {unit.uuid: unit.name for unit, _nodes in units}
            if not names:
                continue
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
                    UnitErrorCount(
                        unit_name=name,
                        error_count=counts.get(unit_uuid, 0),
                    )
                    for unit_uuid, name in names.items()
                ),
                key=attrgetter("error_count"),
                reverse=True,
            )[: self.UNIT_SUMMARY_LIMIT]
            rows.append(
                Notification(
                    create_datetime=datetime.now(UTC),
                    type=NotificationType.UNIT_DAILY_SUMMARY.value,
                    data=UnitDailySummaryData(units=ranked).model_dump(),
                    is_read=False,
                    is_processed=False,
                    user_uuid=user.uuid,
                )
            )
        return self.notification_repository.bulk_create(rows)

    async def process_pending(self) -> int:
        self.is_notification_enable()
        pending = self.notification_repository.lock_unprocessed(
            settings.pu_notification_data_pipe_alert_batch
        )
        outgoing = []
        for notification, user, settings_row in pending:
            try:
                payload = self.PAYLOADS[NotificationType(notification.type)]
                notification.text = payload.model_validate(
                    notification.data
                ).text
            except (KeyError, TypeError, ValueError) as err:
                logging.error(
                    f"Notification {notification.uuid} ({notification.type}) "
                    f"payload is invalid: {err}"
                )
            else:
                if (
                    user.status == UserStatus.VERIFIED.value
                    and settings_row.allows(notification.type)
                ):
                    outgoing.append(
                        NotificationDelivery.Outgoing(
                            user_uuid=user.uuid,
                            chat_id=user.telegram_chat_id,
                            telegram=settings_row.is_telegram_alert_enable,
                            notification_type=NotificationType(
                                notification.type
                            ),
                            text=notification.text,
                            sse_body=NotificationRead(
                                **notification.dict()
                            ).model_dump_json(),
                        )
                    )
            notification.is_processed = True

        self.notification_repository.mark_processed(
            [notification for notification, _user, _settings_row in pending]
        )
        await notification_delivery.deliver(outgoing)
        return len(pending)
