import uuid as uuid_pkg

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.dto.enum import UserStatus
from app.repositories.base_repository import BaseRepository


class NotificationSettingsRepository(BaseRepository[NotificationSettings]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(NotificationSettings, db)

    def get_by_user(
        self, user_uuid: uuid_pkg.UUID
    ) -> NotificationSettings | None:
        return (
            self.db.query(NotificationSettings)
            .filter(NotificationSettings.user_uuid == user_uuid)
            .first()
        )

    def get_or_create(self, user_uuid: uuid_pkg.UUID) -> NotificationSettings:
        settings_row = self.get_by_user(user_uuid)
        if settings_row:
            return settings_row
        return self.create(NotificationSettings.for_user(user_uuid))

    def list_scheduled(
        self, scheduled_notification_time: str
    ) -> list[tuple[User, NotificationSettings]]:
        return (
            self.db.query(User, NotificationSettings)
            .join(
                NotificationSettings,
                NotificationSettings.user_uuid == User.uuid,
            )
            .filter(
                NotificationSettings.is_scheduled_alert_enable.is_(True),
                NotificationSettings.scheduled_notification_time
                == scheduled_notification_time,
                User.status == UserStatus.VERIFIED.value,
            )
            .all()
        )

    def list_data_pipe_enabled(
        self,
    ) -> list[tuple[User, NotificationSettings]]:
        return (
            self.db.query(User, NotificationSettings)
            .join(
                NotificationSettings,
                NotificationSettings.user_uuid == User.uuid,
            )
            .filter(
                NotificationSettings.is_data_pipe_alert_enable.is_(True),
                User.status == UserStatus.VERIFIED.value,
            )
            .all()
        )
