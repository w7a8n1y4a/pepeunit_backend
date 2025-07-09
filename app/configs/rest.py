from typing import Optional

from clickhouse_driver import Client
from fastapi import Depends
from sqlmodel import Session

from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.metrics_service import MetricsService
from app.services.permission_service import PermissionService
from app.services.repo_service import RepoService
from app.services.repository_registry_service import RepositoryRegistryService
from app.services.unit_node_service import UnitNodeService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.services.utils import token_depends


def get_user_service(
    db: Session = Depends(get_session), jwt_token: Optional[str] = Depends(token_depends), is_bot_auth: bool = False
) -> UserService:
    user_repository = UserRepository(db)

    return UserService(
        user_repository=user_repository,
        access_service=AccessService(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=user_repository,
            jwt_token=jwt_token,
            is_bot_auth=is_bot_auth,
        ),
    )


def get_repository_registry_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
    is_bot_auth: bool = False,
) -> RepositoryRegistryService:
    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)
    permission_repository = PermissionRepository(db)
    repository_registry_repository = RepositoryRegistryRepository(db)

    access_service = AccessService(
        permission_repository=permission_repository,
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
        jwt_token=jwt_token,
        is_bot_auth=is_bot_auth,
    )

    permission_service = PermissionService(
        access_service=access_service,
        permission_repository=permission_repository,
    )

    return RepositoryRegistryService(
        repository_registry_repository=repository_registry_repository,
        repo_repository=repo_repository,
        permission_service=permission_service,
        access_service=access_service,
    )


def get_repo_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
    is_bot_auth: bool = False,
) -> RepoService:
    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)
    permission_repository = PermissionRepository(db)
    repository_registry_repository = RepositoryRegistryRepository(db)

    access_service = AccessService(
        permission_repository=permission_repository,
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
        jwt_token=jwt_token,
        is_bot_auth=is_bot_auth,
    )

    permission_service = PermissionService(
        access_service=access_service,
        permission_repository=permission_repository,
    )

    unit_node_service = UnitNodeService(
        unit_repository=unit_repository,
        repo_repository=repo_repository,
        unit_node_repository=UnitNodeRepository(db),
        unit_log_repository=UnitLogRepository(client),
        data_pipe_repository=DataPipeRepository(client),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        access_service=access_service,
        permission_service=permission_service,
    )

    return RepoService(
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        repository_registry_service=RepositoryRegistryService(
            repository_registry_repository=repository_registry_repository,
            permission_service=permission_service,
            access_service=access_service,
        ),
        unit_service=UnitService(
            repo_repository=repo_repository,
            unit_repository=unit_repository,
            unit_node_repository=UnitNodeRepository(db),
            unit_log_repository=UnitLogRepository(client),
            access_service=access_service,
            permission_service=permission_service,
            unit_node_service=unit_node_service,
        ),
        permission_service=permission_service,
        access_service=access_service,
    )


def get_unit_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
    is_bot_auth: bool = False,
) -> UnitService:
    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)
    repository_registry_repository = RepositoryRegistryRepository(db)
    permission_repository = PermissionRepository(db)

    access_service = AccessService(
        permission_repository=permission_repository,
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
        jwt_token=jwt_token,
        is_bot_auth=is_bot_auth,
    )

    permission_service = PermissionService(
        access_service=access_service,
        permission_repository=permission_repository,
    )

    unit_node_service = UnitNodeService(
        unit_repository=unit_repository,
        repository_registry_repository=repository_registry_repository,
        repo_repository=repo_repository,
        unit_node_repository=UnitNodeRepository(db),
        unit_log_repository=UnitLogRepository(client),
        data_pipe_repository=DataPipeRepository(client),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        permission_service=permission_service,
        access_service=access_service,
    )

    return UnitService(
        repository_registry_repository=repository_registry_repository,
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        unit_node_repository=UnitNodeRepository(db),
        unit_log_repository=UnitLogRepository(client),
        access_service=access_service,
        permission_service=permission_service,
        unit_node_service=unit_node_service,
    )


def get_unit_node_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
    is_bot_auth: bool = False,
) -> UnitNodeService:
    unit_repository = UnitRepository(db)
    permission_repository = PermissionRepository(db)

    access_service = AccessService(
        permission_repository=permission_repository,
        unit_repository=unit_repository,
        user_repository=UserRepository(db),
        jwt_token=jwt_token,
        is_bot_auth=is_bot_auth,
    )

    permission_service = PermissionService(
        access_service=access_service,
        permission_repository=permission_repository,
    )

    return UnitNodeService(
        unit_repository=unit_repository,
        repo_repository=RepoRepository(db),
        unit_node_repository=UnitNodeRepository(db),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        unit_log_repository=UnitLogRepository(client),
        data_pipe_repository=DataPipeRepository(client),
        permission_service=permission_service,
        access_service=access_service,
    )


def get_metrics_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
    is_bot_auth: bool = False,
) -> MetricsService:
    repo_repository = RepoRepository(db)
    unit_repository = UnitRepository(db)
    user_repository = UserRepository(db)

    return MetricsService(
        repo_repository=repo_repository,
        unit_repository=unit_repository,
        unit_node_repository=UnitNodeRepository(db),
        unit_node_edge_repository=UnitNodeEdgeRepository(db),
        user_repository=user_repository,
        access_service=AccessService(
            permission_repository=PermissionRepository(db),
            unit_repository=unit_repository,
            user_repository=user_repository,
            jwt_token=jwt_token,
            is_bot_auth=is_bot_auth,
        ),
    )


def get_permission_service(
    db: Session = Depends(get_session), jwt_token: Optional[str] = Depends(token_depends), is_bot_auth: bool = False
) -> PermissionService:
    return PermissionService(
        access_service=AccessService(
            permission_repository=PermissionRepository(db),
            unit_repository=UnitRepository(db),
            user_repository=UserRepository(db),
            jwt_token=jwt_token,
            is_bot_auth=is_bot_auth,
        ),
        permission_repository=PermissionRepository(db),
    )
