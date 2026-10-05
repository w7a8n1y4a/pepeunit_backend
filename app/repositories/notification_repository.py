import uuid as uuid_pkg
from datetime import datetime

from fastapi import Depends
from sqlalchemy import update
from sqlmodel import Session, col

from app.configs.db import get_session
from app.domain.notification_model import Notification
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.gql.inputs.notification import NotificationFilterInput
from app.schemas.pydantic.notification import NotificationFilter


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Notification, db)

    def list(
        self,
        user_uuid: uuid_pkg.UUID,
        filters: NotificationFilter | NotificationFilterInput,
    ) -> tuple[int, list[Notification]]:
        query = self.db.query(Notification).filter(
            Notification.user_uuid == user_uuid
        )

        if filters.is_read is not None:
            query = query.filter(Notification.is_read == filters.is_read)

        query = apply_enums(query, filters, {"type": Notification.type})

        query = query.order_by(col(Notification.create_datetime).desc())
        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def exists_since(
        self,
        user_uuid: uuid_pkg.UUID,
        notification_type: str,
        since: datetime,
        unit_uuid: str | None = None,
    ) -> bool:
        query = self.db.query(Notification).filter(
            Notification.user_uuid == user_uuid,
            Notification.type == notification_type,
            Notification.create_datetime >= since,
        )
        if unit_uuid is not None:
            query = query.filter(
                Notification.data["unit_uuid"].astext == unit_uuid
            )
        return query.first() is not None

    def mark_all_read(
        self, user_uuid: uuid_pkg.UUID, read_datetime: datetime
    ) -> int:
        result = self.db.execute(
            update(Notification)
            .where(
                Notification.user_uuid == user_uuid,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_datetime=read_datetime)
        )
        self.db.commit()
        return result.rowcount or 0
