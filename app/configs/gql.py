from fastapi import Depends
from strawberry.types import Info

from app.services.repo_service import RepoService
from app.services.unit_service import UnitService
from app.services.user_service import UserService


async def get_graphql_context(
    user_service: UserService = Depends(), repo_service: RepoService = Depends(), unit_service: UnitService = Depends()
):
    return {'user_service': user_service, 'repo_service': repo_service, 'unit_service': unit_service}


def get_user_service(info: Info) -> UserService:
    return info.context['user_service']


def get_repo_service(info: Info) -> RepoService:
    return info.context['repo_service']


def get_unit_service(info: Info) -> UnitService:
    return info.context['unit_service']
