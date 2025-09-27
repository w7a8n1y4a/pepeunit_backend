import uuid as uuid_pkg
from typing import TYPE_CHECKING

import strawberry
from strawberry.types import Info

from app import settings
from app.configs.gql import get_user_service_gql
from app.dto.enum import CookieName
from app.schemas.gql.inputs.user import UserAuthInput, UserFilterInput
from app.schemas.gql.types.user import UsersResultType, UserType

if TYPE_CHECKING:
    from strawberry.http.typevars import Response


@strawberry.field()
def get_user(uuid: uuid_pkg.UUID, info: Info) -> UserType:
    user_service = get_user_service_gql(info)
    return UserType(**user_service.get(uuid).dict())


@strawberry.field()
def get_token(data: UserAuthInput, info: Info) -> str:
    user_service = get_user_service_gql(info)

    user_token = user_service.get_token(data)

    info.context["jwt_token"] = user_token
    authorized_user_service = get_user_service_gql(info)

    response: Response = info.context["response"]
    response.set_cookie(
        key=CookieName.PEPEUNIT_GRAFANA.value,
        value=authorized_user_service.get_grafana_token(),
        httponly=True,
        samesite="lax",
        secure=settings.backend_secure,
    )

    return user_token


@strawberry.field()
async def get_verification_user(info: Info) -> str:
    user_service = get_user_service_gql(info)
    return await user_service.generate_verification_link()


@strawberry.field()
def get_users(filters: UserFilterInput, info: Info) -> UsersResultType:
    user_service = get_user_service_gql(info)
    count, users = user_service.list(filters)
    return UsersResultType(
        count=count, users=[UserType(**user.dict()) for user in users]
    )
