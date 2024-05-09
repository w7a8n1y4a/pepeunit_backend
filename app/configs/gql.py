from fastapi import Depends
from sqlmodel import Session
from strawberry.types import Info

from app.configs.db import get_session
from app.services.repo_service import RepoService
from app.services.unit_node_service import UnitNodeService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.services.utils import token_depends


async def get_graphql_context(
    db: Session = Depends(get_session),
    jwt_token: str = Depends(token_depends),
):
    return {
        'db': db,
        'jwt_token': jwt_token
    }


def get_user_service(info: Info) -> UserService:
    return UserService(info.context['db'], info.context['jwt_token'])


def get_repo_service(info: Info) -> RepoService:
    return RepoService(info.context['db'], info.context['jwt_token'])


def get_unit_service(info: Info) -> UnitService:
    return UnitService(info.context['db'], info.context['jwt_token'])


def get_unit_node_service(info: Info) -> UnitNodeService:
    return UnitNodeService(info.context['db'], info.context['jwt_token'])
