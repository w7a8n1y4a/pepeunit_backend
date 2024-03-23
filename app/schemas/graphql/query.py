from typing import List, Optional

import strawberry
from strawberry.types import Info

from app.configs.gql import get_user_service
from app.schemas.graphql.user import UserType


@strawberry.type(description="Query all entities")
class Query:
    @strawberry.field(description="Get an Author")
    def get_user(
        self, uuid: str, info: Info
    ) -> Optional[UserType]:
        user_service = get_user_service(info)
        return UserType(**user_service.get(uuid).dict())
