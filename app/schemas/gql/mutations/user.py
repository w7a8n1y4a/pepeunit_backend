import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service
from app.schemas.gql.inputs.user import UserCreateInput, UserUpdateInput
from app.schemas.gql.types.shared import NoneType
from app.schemas.gql.types.user import UserType


@strawberry.mutation
def create_user(info: Info, user: UserCreateInput) -> UserType:
    user_service = get_user_service(info)
    return UserType(**user_service.create(user).dict())


@strawberry.mutation
def update_user(info: Info, uuid: str, user: UserUpdateInput) -> UserType:
    user_service = get_user_service(info)
    user = user_service.update(uuid, user).dict()
    return UserType(**user)


@strawberry.mutation
def block_user(info: Info, uuid: str) -> NoneType:
    user_service = get_user_service(info)
    user_service.block(uuid)
    return NoneType()


@strawberry.mutation
def unblock_user(info: Info, uuid: str) -> NoneType:
    user_service = get_user_service(info)
    user_service.unblock(uuid)
    return NoneType()
