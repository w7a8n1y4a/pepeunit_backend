import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry

from app.repositories.enum import UserRole, UserStatus, OrderByDate


class BaseMixin:
    def dict(self):
        return self.__dict__


@strawberry.type()
class UserType:
    uuid: uuid_pkg.UUID
    role: UserRole
    status: UserStatus
    login: str
    email: str
    create_datetime: datetime

    hashed_password: strawberry.Private[object]
    cipher_dynamic_salt: strawberry.Private[object]


@strawberry.input()
class UserCreateInput(BaseMixin):
    login: str
    email: str
    password: str


@strawberry.input()
class UserUpdateInput(BaseMixin):
    login: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


@strawberry.input()
class UserFilterInput(BaseMixin):
    search_string: Optional[str] = None

    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
