import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service
from app.schemas.graphql.user import UserCreateInput, UserType, UserUpdateInput


@strawberry.type()
class Mutation:
    @strawberry.field()
    def create_user(
        self, user: UserCreateInput, info: Info
    ) -> UserType:
        user_service = get_user_service(info)
        return UserType(**user_service.create(user).dict())

    @strawberry.field()
    def update_user(
        self, uuid: str, user: UserUpdateInput, info: Info
    ) -> UserType:
        user_service = get_user_service(info)
        user = user_service.update(uuid, user).dict()
        print(user)
        return UserType(**user)

    @strawberry.field()
    def delete_user(
        self, uuid: str, info: Info
    ) -> None:
        user_service = get_user_service(info)
        user_service.delete(uuid)
        return None
