import enum
from typing import Optional

from fastapi import Depends
from fastapi_filter.contrib.sqlalchemy import Filter
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.domain import User
from app.repositories.enum import OrderByDate
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by


class UserRole(enum.Enum):
    """Роль пользователя"""

    USER = 'User'
    ADMIN = 'Admin'


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
        self.db.delete(user)
        self.db.commit()
        self.db.flush()

    def list(self, filters: UserFilter) -> list[User]:
        query = self.db.query(User)

        fields = [User.login, User.email]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {UserFilter.role: User.role, UserFilter.status: User.status}
        query = apply_enums(query, filters, fields)

        query = apply_offset_and_limit(query, filters)

        fields = {UserFilter.order_by_create_date: User.create_datetime}
        query = apply_orders_by(query, filters, fields)

        return query.all()
