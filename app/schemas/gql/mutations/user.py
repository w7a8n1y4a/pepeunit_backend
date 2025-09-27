import uuid as uuid_pkg
from typing import TYPE_CHECKING

import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service_gql
from app.dto.enum import CookieName
from app.schemas.gql.inputs.user import UserCreateInput, UserUpdateInput
from app.schemas.gql.types.shared import NoneType
from app.schemas.gql.types.user import UserType

if TYPE_CHECKING:
    from strawberry.http.typevars import Response


@strawberry.mutation()
def create_user(info: Info, user: UserCreateInput) -> UserType:
    user_service = get_user_service_gql(info)
    return UserType(**user_service.create(user).dict())


@strawberry.mutation()
def update_user(info: Info, user: UserUpdateInput) -> UserType:
    user_service = get_user_service_gql(info)
    user = user_service.update(user).dict()
    return UserType(**user)


@strawberry.mutation()
def block_user(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    user_service = get_user_service_gql(info)
    user_service.block(uuid)
    return NoneType()


@strawberry.mutation()
def unblock_user(info: Info, uuid: uuid_pkg.UUID) -> NoneType:
    user_service = get_user_service_gql(info)
    user_service.unblock(uuid)
    return NoneType()


@strawberry.mutation()
def delete_user_cookies(info: Info) -> NoneType:
    response: Response = info.context["response"]
    response.delete_cookie(CookieName.PEPEUNIT_GRAFANA.value)

    return NoneType()
