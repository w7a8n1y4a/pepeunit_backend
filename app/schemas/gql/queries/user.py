import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service
from app.schemas.gql.inputs.user import UserAuthInput, UserFilterInput
from app.schemas.gql.types.user import UserType


@strawberry.field()
def get_user(
    uuid: str, info: Info
) -> UserType:
    user_service = get_user_service(info)
    return UserType(**user_service.get(uuid).dict())


@strawberry.field()
def get_token(
    data: UserAuthInput, info: Info
) -> str:
    user_service = get_user_service(info)
    return user_service.get_token(data)


@strawberry.field()
def get_users(
    filters: UserFilterInput, info: Info
) -> list[UserType]:
    user_service = get_user_service(info)
    return [UserType(**user.dict()) for user in user_service.list(filters)]
