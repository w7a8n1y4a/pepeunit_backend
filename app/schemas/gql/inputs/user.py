import uuid as uuid_pkg
from typing import Optional

import strawberry

from app.repositories.enum import OrderByDate, UserRole, UserStatus
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UserAuthInput(TypeInputMixin):
    credentials: str
    password: str


@strawberry.input()
class UserCreateInput(TypeInputMixin):
    login: str
    password: str


@strawberry.input()
class UserUpdateInput(TypeInputMixin):
    login: Optional[str] = None
    password: Optional[str] = None


@strawberry.input()
class UserFilterInput(TypeInputMixin):
    uuids: Optional[list[uuid_pkg.UUID]] = tuple()

    search_string: Optional[str] = None

    role: Optional[list[UserRole]] = tuple([item for item in UserRole])
    status: Optional[list[UserStatus]] = tuple([item for item in UserStatus])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
