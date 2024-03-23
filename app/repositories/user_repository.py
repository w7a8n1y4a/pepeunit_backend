import enum
from typing import Optional

import strawberry
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status
from fastapi_filter.contrib.sqlalchemy import Filter
from sqlalchemy.orm import Session
from sqlmodel import Session, select, func

from app.core.db import get_session
from app.domain.user_model import User
from app.repositories.enum import OrderByDate
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by

@strawberry.enum
class UserRole(enum.Enum):
    """Роль пользователя"""

    USER = 'User'
    ADMIN = 'Admin'

@strawberry.enum
class UserStatus(enum.Enum):
    """Статус пользователя"""

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'


class UserFilter(Filter):
    """Фильтр выборки пользователей"""

    search_string: Optional[str] = None

    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


class UserRepository:
    db: Session

    def __init__(
        self, db: Session = Depends(get_session)
    ) -> None:
        self.db = db

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get(self, user: User) -> User:
        return self.db.get(User, user.uuid)

    def update(self, uuid, user: User) -> User:
        user.uuid = uuid
        self.db.merge(user)
        self.db.commit()
        return user

    def delete(self, user: User) -> None:
        self.db.delete(self.get(user))
        self.db.commit()
        self.db.flush()

    def list(self, filters: UserFilter) -> list[User]:
        query = self.db.query(User)

        fields = [User.login, User.email]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'role': User.role, 'status': User.status}
        query = apply_enums(query, filters, fields)

        fields = {'order_by_create_date': User.create_datetime}
        query = apply_orders_by(query, filters, fields)

        query = apply_offset_and_limit(query, filters)
        return query.all()

    def is_valid_login(self, login: str, uuid: str = None):
        user_uuid = self.db.exec(select(User.uuid).where(User.login == login)).first()
        user_uuid = str(user_uuid) if user_uuid else user_uuid

        if (uuid is None and user_uuid) or (uuid and user_uuid != uuid and user_uuid is not None):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Login is not unique")

    def is_valid_email(self, email: str, uuid: str = None):
        user_uuid = self.db.exec(select(User.uuid).where(User.email == email)).first()
        user_uuid = str(user_uuid) if user_uuid else user_uuid

        if (uuid is None and user_uuid) or (uuid and user_uuid != uuid and user_uuid is not None):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Email is not unique")
