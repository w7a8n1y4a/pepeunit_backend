from fastapi import Depends
from sqlmodel import Session
from strawberry.types import Info

from app.configs.db import get_session
from app.repositories.permission_repository import PermissionRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.metrics_service import MetricsService
from app.services.permission_service import PermissionService
from app.services.repo_service import RepoService
from app.services.unit_node_service import UnitNodeService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.services.utils import token_depends


async def get_graphql_context(
    db: Session = Depends(get_session),
    jwt_token: str = Depends(token_depends),
):
    return {'db': db, 'jwt_token': jwt_token}


def get_access_service(info: Info) -> type[AccessService]:
    if 'is_bot_auth' in info.context and info.context['is_bot_auth']:
        access_service = AccessService
        access_service._is_bot_auth = info.context['is_bot_auth']

        return access_service
    else:
        return AccessService


def get_user_service(info: Info) -> UserService:
    db = info.context['db']
    jwt_token = info.context['jwt_token']

    user_repository = UserRepository(db)

    return UserService(
        user_repository=user_repository,
        access_service=get_access_service(info)(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=user_repository,
            jwt_token=jwt_token,
        ),
    )


def get_repo_service(info: Info) -> RepoService:
    db = info.context['db']
    jwt_token = info.context['jwt_token']

    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)

    access_service = get_access_service(info)(
        permission_repository=PermissionRepository(db),
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
        jwt_token=jwt_token,
    )

    unit_node_service = UnitNodeService(
        unit_node_repository=UnitNodeRepository(db),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        access_service=access_service,
    )

    return RepoService(
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        unit_service=UnitService(
            repo_repository=repo_repository,
            unit_repository=unit_repository,
            unit_node_repository=UnitNodeRepository(db),
            access_service=access_service,
            unit_node_service=unit_node_service,
        ),
        access_service=access_service,
    )


def get_unit_service(info: Info) -> UnitService:
    db = info.context['db']
    jwt_token = info.context['jwt_token']

    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)

    access_service = get_access_service(info)(
        permission_repository=PermissionRepository(db),
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
        jwt_token=jwt_token,
    )

    unit_node_service = UnitNodeService(
        unit_node_repository=UnitNodeRepository(db),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        access_service=access_service,
    )

    return UnitService(
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        unit_node_repository=UnitNodeRepository(db),
        access_service=access_service,
        unit_node_service=unit_node_service,
    )


def get_unit_node_service(info: Info) -> UnitNodeService:
    db = info.context['db']
    jwt_token = info.context['jwt_token']

    return UnitNodeService(
        unit_node_repository=UnitNodeRepository(db),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        access_service=get_access_service(info)(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=UserRepository(db),
            jwt_token=jwt_token,
        ),
    )


def get_metrics_service(info: Info) -> MetricsService:
    db = info.context['db']
    jwt_token = info.context['jwt_token']

    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)
    user_repository = UserRepository(db)

    return MetricsService(
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        unit_node_repository=UnitNodeRepository(db),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        user_repository=user_repository,
        access_service=get_access_service(info)(
            permission_repository=PermissionRepository(db),
            unit_repository=unit_repository,
            user_repository=user_repository,
            jwt_token=jwt_token,
        ),
    )


def get_permission_service(info: Info) -> PermissionService:
    db = info.context['db']
    jwt_token = info.context['jwt_token']

    return PermissionService(
        access_service=get_access_service(info)(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=UserRepository(db),
            jwt_token=jwt_token,
        ),
    )
