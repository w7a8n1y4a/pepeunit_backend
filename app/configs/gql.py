from fastapi import Depends
from sqlmodel import Session
from strawberry.types import Info

from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.services.metrics_service import MetricsService
from app.services.permission_service import PermissionService
from app.services.repo_service import RepoService
from app.services.unit_node_service import UnitNodeService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.services.utils import token_depends


async def get_graphql_context(
    db: Session = Depends(get_session),
    clickhouse_client: Session = Depends(get_clickhouse_client),
    jwt_token: str = Depends(token_depends),
):
    return {'db': db, 'clickhouse_client': clickhouse_client, 'jwt_token': jwt_token}


def get_user_service(info: Info) -> UserService:
    db = info.context.get('db')
    jwt_token = info.context['jwt_token']
    return UserService(db, jwt_token)


def get_repo_service(info: Info) -> RepoService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return RepoService(db, clickhouse_client, jwt_token)


def get_unit_service(info: Info) -> UnitService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return UnitService(db, clickhouse_client, jwt_token)


def get_unit_node_service(info: Info) -> UnitNodeService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return UnitNodeService(db, clickhouse_client, jwt_token)


def get_metrics_service(info: Info) -> MetricsService:
    db = info.context.get('db')
    jwt_token = info.context['jwt_token']
    return MetricsService(db, jwt_token)


def get_permission_service(info: Info) -> PermissionService:
    db = info.context.get('db')
    jwt_token = info.context['jwt_token']
    return PermissionService(db, jwt_token)
