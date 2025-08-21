import uuid as uuid_pkg

import strawberry
from strawberry.http.typevars import Response
from strawberry.types import Info

from app import settings
from app.configs.gql import get_user_service_gql
from app.dto.enum import CookieName
from app.schemas.gql.inputs.user import UserAuthInput, UserFilterInput
from app.schemas.gql.types.user import UsersResultType, UserType


@strawberry.field()
def get_user(uuid: uuid_pkg.UUID, info: Info) -> UserType:
    user_service = get_user_service_gql(info)
    return UserType(**user_service.get(uuid).dict())


@strawberry.field()
def get_token(data: UserAuthInput, info: Info) -> str:
    user_service = get_user_service_gql(info)
    return user_service.get_token(data)


@strawberry.field()
def get_grafana_token(info: Info) -> str:
    user_service = get_user_service_gql(info)

    token = user_service.get_grafana_token()

    response: Response = info.context["response"]
    response.set_cookie(
        key=CookieName.PEPEUNIT_GRAFANA.value,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.backend_secure,
    )

    return token


@strawberry.field()
async def get_verification_user(info: Info) -> str:
    user_service = get_user_service_gql(info)
    return await user_service.generate_verification_link()


@strawberry.field()
def get_users(filters: UserFilterInput, info: Info) -> UsersResultType:
    user_service = get_user_service_gql(info)
    count, users = user_service.list(filters)
    return UsersResultType(count=count, users=[UserType(**user.dict()) for user in users])
