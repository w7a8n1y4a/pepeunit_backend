from clickhouse_driver import Client
from fastapi import Depends
from sqlmodel import Session

from app import runtime
from app.configs.clickhouse import get_clickhouse_client
from app.configs.db import get_session
from app.configs.error_codes import ErrorCode
from app.configs.errors import FeatureFlagError
from app.repositories.dashboard_panel_repository import (
    DashboardPanelRepository,
)
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.icon_repository import IconRepository
from app.repositories.instance_settings_repository import (
    InstanceSettingsRepository,
)
from app.repositories.loki_repository import LokiRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.notification_settings_repository import (
    NotificationSettingsRepository,
)
from app.repositories.operation_task_repository import OperationTaskRepository
from app.repositories.panels_unit_ios_repository import (
    PanelsUnitIOsRepository,
)
from app.repositories.peer_external_repository import (
    PeerExternalRepository,
)
from app.repositories.peer_repository import PeerRepository
from app.repositories.permission_repository import PermissionRepository
from app.repositories.repo_repository import (
    RepoRepository,
)
from app.repositories.unit_group_repository import UnitGroupRepository
from app.repositories.unit_group_unit_repository import (
    UnitGroupUnitRepository,
)
from app.repositories.unit_io_edge_repository import UnitIOEdgeRepository
from app.repositories.unit_io_repository import UnitIORepository
from app.repositories.unit_log_repository import UnitLogRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.access_service import AccessService
from app.services.grafana_service import GrafanaService
from app.services.icon_service import IconService
from app.services.instance_settings_service import InstanceSettingsService
from app.services.metrics_service import MetricsService
from app.services.notification_service import NotificationService
from app.services.operation_task_service import OperationTaskService
from app.services.peer_service import PeerService
from app.services.permission_service import PermissionService
from app.services.repo_service import RepoService
from app.services.unit_group_service import UnitGroupService
from app.services.unit_io_service import UnitIOService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.services.utils import token_depends


class ServiceFactory:
    def __init__(
        self,
        db: Session,
        client: Client | None = None,
        jwt_token: str | None = None,
        is_bot_auth: bool = False,
    ):
        self.db = db
        self.client = client
        self.jwt_token = jwt_token
        self.is_bot_auth = is_bot_auth

        # Initialize repositories
        self.user_repository = UserRepository(db)
        self.icon_repository = IconRepository(db)
        self.unit_repository = UnitRepository(db)
        self.unit_group_repository = UnitGroupRepository(db)
        self.unit_group_unit_repository = UnitGroupUnitRepository(db)
        self.permission_repository = PermissionRepository(db)
        self.repo_repository = RepoRepository(db)
        self.peer_repository = PeerRepository(db)
        self.instance_settings_repository = InstanceSettingsRepository(db)
        self.peer_external_repository = PeerExternalRepository()
        self.loki_repository = LokiRepository()
        self.operation_task_repository = OperationTaskRepository(db)
        self.notification_repository = NotificationRepository(db)
        self.notification_settings_repository = NotificationSettingsRepository(
            db
        )
        self.unit_io_repository = UnitIORepository(db)
        self.unit_io_edge_repository = UnitIOEdgeRepository(db)
        self.unit_log_repository = (
            UnitLogRepository(client) if client else None
        )
        self.data_pipe_repository = (
            DataPipeRepository(client, db) if client else None
        )
        self.dashboard_repository = DashboardRepository(db)
        self.dashboard_panel_repository = DashboardPanelRepository(db)
        self.panels_unit_ios_repository = PanelsUnitIOsRepository(db)

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
            icon_repository=self.icon_repository,
            access_service=self.access_service,
            data_pipe_repository=self.data_pipe_repository,
            notification_settings_repository=(
                self.notification_settings_repository
            ),
        )

    def get_instance_settings_service(self) -> InstanceSettingsService:
        return InstanceSettingsService(
            instance_settings_repository=self.instance_settings_repository,
            operation_task_service=self.get_operation_task_service(),
            access_service=self.access_service,
        )

    def get_icon_service(self) -> IconService:
        return IconService(
            icon_repository=self.icon_repository,
            user_repository=self.user_repository,
            unit_repository=self.unit_repository,
            unit_group_repository=self.unit_group_repository,
            instance_settings_repository=self.instance_settings_repository,
            access_service=self.access_service,
        )

    def get_unit_group_service(self) -> UnitGroupService:
        return UnitGroupService(
            unit_group_repository=self.unit_group_repository,
            unit_group_unit_repository=self.unit_group_unit_repository,
            unit_repository=self.unit_repository,
            icon_repository=self.icon_repository,
            access_service=self.access_service,
        )

    def get_peer_service(self) -> PeerService:
        return PeerService(
            peer_repository=self.peer_repository,
            peer_external_repository=self.peer_external_repository,
            operation_task_repository=self.operation_task_repository,
            repo_repository=self.repo_repository,
            access_service=self.access_service,
            repo_service=self.get_repo_service(),
            metrics_service=self.get_metrics_service(),
            operation_task_service=self.get_operation_task_service(),
        )

    def get_operation_task_service(self) -> OperationTaskService:
        return OperationTaskService(
            operation_task_repository=self.operation_task_repository,
            access_service=self.access_service,
        )

    def get_repo_service(self) -> RepoService:
        return RepoService(
            repo_repository=self.repo_repository,
            icon_repository=self.icon_repository,
            unit_repository=self.unit_repository,
            user_repository=self.user_repository,
            operation_task_service=self.get_operation_task_service(),
            permission_service=self.permission_service,
            access_service=self.access_service,
        )

    def get_unit_service(self) -> UnitService:
        return UnitService(
            repo_repository=self.repo_repository,
            unit_repository=self.unit_repository,
            icon_repository=self.icon_repository,
            unit_io_repository=self.unit_io_repository,
            unit_log_repository=self.unit_log_repository,
            access_service=self.access_service,
            permission_service=self.permission_service,
            operation_task_service=self.get_operation_task_service(),
            unit_io_service=self.get_unit_io_service(),
        )

    def get_unit_io_service(self) -> UnitIOService:
        return UnitIOService(
            unit_repository=self.unit_repository,
            repo_repository=self.repo_repository,
            unit_io_repository=self.unit_io_repository,
            unit_io_edge_repository=self.unit_io_edge_repository,
            unit_log_repository=self.unit_log_repository,
            data_pipe_repository=self.data_pipe_repository,
            permission_service=self.permission_service,
            access_service=self.access_service,
        )

    def get_grafana_service(self) -> GrafanaService:
        if not runtime.get().pu_ff_grafana_integration_enable:
            msg = "This feature has been disabled by the instance Owner"
            raise FeatureFlagError(msg, code=ErrorCode.FEATURE_DISABLED)
        return GrafanaService(
            dashboard_repository=self.dashboard_repository,
            dashboard_panel_repository=self.dashboard_panel_repository,
            panels_unit_ios_repository=self.panels_unit_ios_repository,
            unit_repository=self.unit_repository,
            unit_io_repository=self.unit_io_repository,
            data_pipe_repository=self.data_pipe_repository,
            access_service=self.access_service,
            user_service=self.get_user_service(),
            unit_io_service=self.get_unit_io_service(),
        )

    def get_metrics_service(self) -> MetricsService:
        return MetricsService(
            repo_repository=self.repo_repository,
            unit_repository=self.unit_repository,
            unit_io_repository=self.unit_io_repository,
            unit_io_edge_repository=self.unit_io_edge_repository,
            user_repository=self.user_repository,
            access_service=self.access_service,
        )

    def get_permission_service(self) -> PermissionService:
        return self.permission_service

    def get_notification_service(self) -> NotificationService:
        return NotificationService(
            notification_repository=self.notification_repository,
            notification_settings_repository=(
                self.notification_settings_repository
            ),
            unit_repository=self.unit_repository,
            unit_log_repository=self.unit_log_repository,
            loki_repository=self.loki_repository,
            access_service=self.access_service,
        )


def create_service_factory(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> ServiceFactory:
    return ServiceFactory(db, client, jwt_token, False)


def get_icon_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> IconService:
    return create_service_factory(db, None, jwt_token).get_icon_service()


def get_user_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> UserService:
    return create_service_factory(db, client, jwt_token).get_user_service()


def get_peer_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> PeerService:
    return create_service_factory(db, None, jwt_token).get_peer_service()


def get_instance_settings_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> InstanceSettingsService:
    return create_service_factory(
        db, None, jwt_token
    ).get_instance_settings_service()


def get_operation_task_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> OperationTaskService:
    return create_service_factory(
        db,
        None,
        jwt_token,
    ).get_operation_task_service()


def get_repo_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> RepoService:
    return create_service_factory(db, None, jwt_token).get_repo_service()


def get_unit_group_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> UnitGroupService:
    return create_service_factory(db, None, jwt_token).get_unit_group_service()


def get_unit_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> UnitService:
    return create_service_factory(db, client, jwt_token).get_unit_service()


def get_unit_io_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> UnitIOService:
    return create_service_factory(db, client, jwt_token).get_unit_io_service()


def get_grafana_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> GrafanaService:
    return create_service_factory(db, client, jwt_token).get_grafana_service()


def get_metrics_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> MetricsService:
    return create_service_factory(db, None, jwt_token).get_metrics_service()


def get_permission_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> PermissionService:
    return create_service_factory(db, None, jwt_token).get_permission_service()


def get_notification_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> NotificationService:
    return create_service_factory(
        db, client, jwt_token
    ).get_notification_service()


def create_bot_service_factory(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> ServiceFactory:
    return ServiceFactory(db, client, jwt_token, True)


def get_bot_user_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> UserService:
    return create_bot_service_factory(db, client, jwt_token).get_user_service()


def get_bot_repo_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> RepoService:
    return create_bot_service_factory(db, None, jwt_token).get_repo_service()


def get_bot_unit_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> UnitService:
    return create_bot_service_factory(db, client, jwt_token).get_unit_service()


def get_bot_unit_io_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> UnitIOService:
    return create_bot_service_factory(
        db, client, jwt_token
    ).get_unit_io_service()


def get_bot_grafana_service(
    db: Session = Depends(get_session),
    client: Client = Depends(get_clickhouse_client),
    jwt_token: str | None = Depends(token_depends),
) -> GrafanaService:
    return create_bot_service_factory(
        db, client, jwt_token
    ).get_grafana_service()


def get_bot_metrics_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> MetricsService:
    return create_bot_service_factory(
        db, None, jwt_token
    ).get_metrics_service()


def get_bot_peer_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> PeerService:
    return create_bot_service_factory(db, None, jwt_token).get_peer_service()


def get_bot_notification_service(
    db: Session = Depends(get_session),
    jwt_token: str | None = Depends(token_depends),
) -> NotificationService:
    return create_bot_service_factory(
        db, None, jwt_token
    ).get_notification_service()
