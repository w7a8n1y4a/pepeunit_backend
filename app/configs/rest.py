from typing import Optional

from clickhouse_driver import Client
from fastapi import Depends
from sqlmodel import Session

from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.repositories.dashboard_panel_repository import DashboardPanelRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.panels_unit_nodes_repository import PanelsUnitNodesRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import RepositoryRegistryRepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.grafana_service import GrafanaService
from app.services.metrics_service import MetricsService
from app.services.permission_service import PermissionService
from app.services.repo_service import RepoService
from app.services.repository_registry_service import RepositoryRegistryService
from app.services.unit_node_service import UnitNodeService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.services.utils import token_depends


class ServiceFactory:
    def __init__(
        self,
        db: Session,
        client: Optional[Client] = None,
        jwt_token: Optional[str] = None,
        is_bot_auth: bool = False,
    ):
        self.db = db
        self.client = client
        self.jwt_token = jwt_token
        self.is_bot_auth = is_bot_auth

        # Initialize repositories
        self.user_repository = UserRepository(db)
        self.unit_repository = UnitRepository(db)
        self.permission_repository = PermissionRepository(db)
        self.repo_repository = RepoRepository(db)
        self.repository_registry_repository = RepositoryRegistryRepository(db)
        self.unit_node_repository = UnitNodeRepository(db)
        self.unit_node_edge_repository = UnitNodeEdgeRepository(db)
        self.unit_log_repository = UnitLogRepository(client) if client else None
        self.data_pipe_repository = DataPipeRepository(client, db) if client else None
        self.dashboard_repository = DashboardRepository(db)
        self.dashboard_panel_repository = DashboardPanelRepository(db)
        self.panels_unit_nodes_repository = PanelsUnitNodesRepository(db)

        # Initialize services
        self.access_service = AccessService(
            permission_repository=self.permission_repository,
            unit_repository=self.unit_repository,
            user_repository=self.user_repository,
            jwt_token=jwt_token,
            is_bot_auth=is_bot_auth,
        )

        self.permission_service = PermissionService(
            access_service=self.access_service,
            permission_repository=self.permission_repository,
        )

    def get_user_service(self) -> UserService:
        return UserService(
            user_repository=self.user_repository,
            access_service=self.access_service,
            data_pipe_repository=self.data_pipe_repository,
        )

    def get_repository_registry_service(self) -> RepositoryRegistryService:
        return RepositoryRegistryService(
            repository_registry_repository=self.repository_registry_repository,
            repo_repository=self.repo_repository,
            permission_service=self.permission_service,
            access_service=self.access_service,
        )

    def get_repo_service(self) -> RepoService:
        return RepoService(
            repo_repository=self.repo_repository,
            unit_repository=self.unit_repository,
            repository_registry_service=self.get_repository_registry_service(),
            unit_service=UnitService(
                repo_repository=self.repo_repository,
                unit_repository=self.unit_repository,
                unit_node_repository=self.unit_node_repository,
                unit_log_repository=self.unit_log_repository,
                access_service=self.access_service,
                permission_service=self.permission_service,
                unit_node_service=self.get_unit_node_service(),
            ),
            permission_service=self.permission_service,
            access_service=self.access_service,
        )

    def get_unit_service(self) -> UnitService:
        return UnitService(
            repository_registry_repository=self.repository_registry_repository,
            repo_repository=self.repo_repository,
            unit_repository=self.unit_repository,
            unit_node_repository=self.unit_node_repository,
            unit_log_repository=self.unit_log_repository,
            access_service=self.access_service,
            permission_service=self.permission_service,
            unit_node_service=self.get_unit_node_service(),
        )

    def get_unit_node_service(self) -> UnitNodeService:
        return UnitNodeService(
            unit_repository=self.unit_repository,
            repository_registry_repository=self.repository_registry_repository,
            repo_repository=self.repo_repository,
            unit_node_repository=self.unit_node_repository,
            unit_node_edge_repository=self.unit_node_edge_repository,
            unit_log_repository=self.unit_log_repository,
            data_pipe_repository=self.data_pipe_repository,
            permission_service=self.permission_service,
            access_service=self.access_service,
        )

    def get_grafana_service(self) -> GrafanaService:
        return GrafanaService(
            dashboard_repository=self.dashboard_repository,
            dashboard_panel_repository=self.dashboard_panel_repository,
            panels_unit_nodes_repository=self.panels_unit_nodes_repository,
            unit_repository=self.unit_repository,
            unit_node_repository=self.unit_node_repository,
            data_pipe_repository=self.data_pipe_repository,
            access_service=self.access_service,
            user_service=self.get_user_service(),
            unit_node_service=self.get_unit_node_service(),
        )

    def get_metrics_service(self) -> MetricsService:
        return MetricsService(
            repository_registry_repository=self.repository_registry_repository,
            repo_repository=self.repo_repository,
            unit_repository=self.unit_repository,
            unit_node_repository=self.unit_node_repository,
            unit_node_edge_repository=self.unit_node_edge_repository,
            user_repository=self.user_repository,
            access_service=self.access_service,
        )

    def get_permission_service(self) -> PermissionService:
        return self.permission_service


def create_service_factory(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> ServiceFactory:
    return ServiceFactory(db, client, jwt_token, False)


def get_user_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> UserService:
    return create_service_factory(db, client, jwt_token).get_user_service()


def get_repository_registry_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
) -> RepositoryRegistryService:
    return create_service_factory(db, None, jwt_token).get_repository_registry_service()


def get_repo_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> RepoService:
    return create_service_factory(db, client, jwt_token).get_repo_service()


def get_unit_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> UnitService:
    return create_service_factory(db, client, jwt_token).get_unit_service()


def get_unit_node_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> UnitNodeService:
    return create_service_factory(db, client, jwt_token).get_unit_node_service()


def get_grafana_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> GrafanaService:
    return create_service_factory(db, client, jwt_token).get_grafana_service()


def get_metrics_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
) -> MetricsService:
    return create_service_factory(db, None, jwt_token).get_metrics_service()


def get_permission_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
) -> PermissionService:
    return create_service_factory(db, None, jwt_token).get_permission_service()


def create_bot_service_factory(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> ServiceFactory:
    return ServiceFactory(db, client, jwt_token, True)


def get_bot_user_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> UserService:
    return create_bot_service_factory(db, client, jwt_token).get_user_service()


def get_bot_repository_registry_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
) -> RepositoryRegistryService:
    return create_bot_service_factory(
        db, None, jwt_token
    ).get_repository_registry_service()


def get_bot_repo_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> RepoService:
    return create_bot_service_factory(db, client, jwt_token).get_repo_service()


def get_bot_unit_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> UnitService:
    return create_bot_service_factory(db, client, jwt_token).get_unit_service()


def get_bot_unit_node_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> UnitNodeService:
    return create_bot_service_factory(db, client, jwt_token).get_unit_node_service()


def get_bot_grafana_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: Optional[str] = Depends(token_depends),
) -> GrafanaService:
    return create_bot_service_factory(db, client, jwt_token).get_grafana_service()


def get_bot_metrics_service(
    db: Session = Depends(get_session),
    jwt_token: Optional[str] = Depends(token_depends),
) -> MetricsService:
    return create_bot_service_factory(db, None, jwt_token).get_metrics_service()
