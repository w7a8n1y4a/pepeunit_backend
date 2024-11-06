import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service
from app.schemas.gql.inputs.user import UserAuthInput, UserFilterInput
from app.schemas.gql.types.user import UsersResultType, UserType


@strawberry.field()
def get_user(uuid: uuid_pkg.UUID, info: Info) -> UserType:
    user_service = get_user_service(info)
    return UserType(**user_service.get(uuid).dict())


@strawberry.field()
def get_token(data: UserAuthInput, info: Info) -> str:
    user_service = get_user_service(info)
    return user_service.get_token(data)


@strawberry.field()
async def get_verification_user(info: Info) -> str:
    user_service = get_user_service(info)
    return await user_service.generate_verification_code()


@strawberry.field()
def get_users(filters: UserFilterInput, info: Info) -> UsersResultType:
    user_service = get_user_service(info)
    count, users = user_service.list(filters)
    return UsersResultType(count=count, users=[UserType(**user.dict()) for user in users])
