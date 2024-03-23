from fastapi import Depends
from strawberry.types import Info

from app.services.user_service import UserService


async def get_graphql_context(
    user_service: UserService = Depends(),
):
    return {
        "user_service": user_service,
    }


# Extract AuthorService instance from GraphQL context
def get_user_service(info: Info) -> UserService:
    return info.context["user_service"]
