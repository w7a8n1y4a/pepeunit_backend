from fastapi import Depends
from sqlmodel import Session
from strawberry.types import Info

from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.configs.rest import (
    get_grafana_service,
    get_metrics_service,
    get_permission_service,
    get_repo_service,
    get_repository_registry_service,
    get_unit_node_service,
    get_unit_service,
    get_user_service,
)
from app.services.grafana_service import GrafanaService
from app.services.metrics_service import MetricsService
from app.services.permission_service import PermissionService
from app.services.repo_service import RepoService
from app.services.repository_registry_service import RepositoryRegistryService
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


def get_user_service_gql(info: Info) -> UserService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return get_user_service(db, clickhouse_client, jwt_token)


def get_repository_registry_service_gql(info: Info) -> RepositoryRegistryService:
    db = info.context.get('db')
    jwt_token = info.context['jwt_token']
    return get_repository_registry_service(db, jwt_token)


def get_repo_service_gql(info: Info) -> RepoService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return get_repo_service(db, clickhouse_client, jwt_token)


def get_unit_service_gql(info: Info) -> UnitService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return get_unit_service(db, clickhouse_client, jwt_token)


def get_unit_node_service_gql(info: Info) -> UnitNodeService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return get_unit_node_service(db, clickhouse_client, jwt_token)


def get_grafana_service_gql(info: Info) -> GrafanaService:
    db = info.context.get('db')
    clickhouse_client = info.context.get('clickhouse_client')
    jwt_token = info.context['jwt_token']
    return get_grafana_service(db, clickhouse_client, jwt_token)


def get_metrics_service_gql(info: Info) -> MetricsService:
    db = info.context.get('db')
    jwt_token = info.context['jwt_token']
    return get_metrics_service(db, jwt_token)


def get_permission_service_gql(info: Info) -> PermissionService:
    db = info.context.get('db')
    jwt_token = info.context['jwt_token']
    return get_permission_service(db, jwt_token)
