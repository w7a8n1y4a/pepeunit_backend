import uuid as uuid_pkg

import strawberry

from app.dto.enum import OrderByDate, UserRole, UserStatus
from app.schemas.gql.type_input_mixin import BasePaginationGql, TypeInputMixin


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
    login: str | None = None
    password: str | None = None


@strawberry.input()
class UserFilterInput(BasePaginationGql):
    uuids: list[uuid_pkg.UUID] | None = ()

    search_string: str | None = None

    role: list[UserRole] | None = tuple(UserRole)
    status: list[UserStatus] | None = tuple(UserStatus)

    order_by_create_date: OrderByDate | None = OrderByDate.desc
