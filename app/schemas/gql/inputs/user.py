from typing import Optional

import strawberry

from app.repositories.enum import UserRole, UserStatus, OrderByDate
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UserAuthInput(TypeInputMixin):
    credentials: str
    password: str


@strawberry.input()
class UserCreateInput(TypeInputMixin):
    login: str
    email: str
    password: str


@strawberry.input()
class UserUpdateInput(TypeInputMixin):
    login: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


@strawberry.input()
class UserFilterInput(TypeInputMixin):
    search_string: Optional[str] = None

    role: list[UserRole] = tuple([item for item in UserRole])
    status: list[UserStatus] = tuple([item for item in UserStatus])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
