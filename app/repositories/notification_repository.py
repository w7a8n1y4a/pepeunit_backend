import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends
from sqlalchemy import update
from sqlmodel import Session, col

from app.configs.db import get_session
from app.domain.notification_model import Notification
from app.domain.notification_settings_model import NotificationSettings
from app.domain.user_model import User
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.gql.inputs.notification import NotificationFilterInput
from app.schemas.pydantic.notification import NotificationFilter


@dataclass(frozen=True)
class PendingNotification:
    """One locked, unprocessed notification and the recipient it belongs to."""

    notification: Notification
    user: User
    settings: NotificationSettings


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Notification, db)

    def get(
        self, obj: Notification, is_visible: bool = False
    ) -> Notification | None:
        query = self.db.query(Notification).filter(
            Notification.uuid == obj.uuid
        )
        if is_visible:
            query = query.filter(
                Notification.is_processed.is_(True),
                Notification.text.is_not(None),
            )
        return query.first()

    def list(
        self,
        user_uuid: uuid_pkg.UUID,
        filters: NotificationFilter | NotificationFilterInput,
        is_visible: bool = False,
    ) -> tuple[int, list[Notification]]:
        query = self.db.query(Notification).filter(
            Notification.user_uuid == user_uuid
        )
        if is_visible:
            query = query.filter(
                Notification.is_processed.is_(True),
                Notification.text.is_not(None),
            )

        if filters.is_read is not None:
            query = query.filter(Notification.is_read == filters.is_read)

        query = apply_enums(query, filters, {"type": Notification.type})

        query = query.order_by(col(Notification.create_datetime).desc())
        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def bulk_create(
        self, notifications: list[Notification]
    ) -> list[Notification]:
        if not notifications:
            return []
        self.db.add_all(notifications)
        self.db.commit()
        return notifications

    def present_since(
        self,
        user_uuids: list[uuid_pkg.UUID],
        notification_types: tuple[str, ...] | list[str],
        since: datetime,
    ) -> set[tuple[uuid_pkg.UUID, str]]:
        """User and type pairs that already have a row in this window."""
        if not user_uuids:
            return set()
        rows = (
            self.db.query(Notification.user_uuid, Notification.type)
            .filter(
                col(Notification.user_uuid).in_(user_uuids),
                col(Notification.type).in_(notification_types),
                Notification.create_datetime >= since,
            )
            .all()
        )
        return {
            (user_uuid, notification_type)
            for user_uuid, notification_type in rows
        }

    def lock_unprocessed(self, limit: int) -> list[PendingNotification]:
        """Locks one batch. Another worker skips these rows."""
        rows = (
            self.db.query(Notification, User, NotificationSettings)
            .join(User, User.uuid == Notification.user_uuid)
            .join(
                NotificationSettings,
                NotificationSettings.user_uuid == User.uuid,
            )
            .filter(Notification.is_processed.is_(False))
            .order_by(col(Notification.create_datetime))
            .limit(limit)
            .with_for_update(skip_locked=True, of=Notification)
            .all()
        )
        return [
            PendingNotification(
                notification=notification,
                user=user,
                settings=settings_row,
            )
            for notification, user, settings_row in rows
        ]

    def mark_processed(
        self, updates: list[tuple[Notification, str | None]]
    ) -> None:
        """Stores the text and closes the row, in one transaction."""
        if not updates:
            return
        for notification, text in updates:
            notification.text = text
            notification.is_processed = True
        self.db.commit()

    def mark_all_read(
        self,
        user_uuid: uuid_pkg.UUID,
        read_datetime: datetime,
        is_visible: bool = False,
    ) -> int:
        statement = update(Notification).where(
            Notification.user_uuid == user_uuid,
            Notification.is_read.is_(False),
        )
        if is_visible:
            statement = statement.where(
                Notification.is_processed.is_(True),
                Notification.text.is_not(None),
            )
        result = self.db.execute(
            statement.values(is_read=True, read_datetime=read_datetime)
        )
        self.db.commit()
        return result.rowcount or 0
