from typing import List, Optional

import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service
from app.schemas.graphql.user import UserType, UserFilterInput


@strawberry.type()
class Query:
    @strawberry.field()
    def get_user(
        self, uuid: str, info: Info
    ) -> UserType:
        user_service = get_user_service(info)
        return UserType(**user_service.get(uuid).dict())

    @strawberry.field()
    def get_users(
        self, filters: UserFilterInput, info: Info
    ) -> list[UserType]:
        user_service = get_user_service(info)
        return [UserType(**user.dict()) for user in user_service.list(filters)]
