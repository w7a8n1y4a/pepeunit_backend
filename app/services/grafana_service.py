import datetime
import json
import uuid as uuid_pkg

from fastapi import Depends

from app import runtime
from app.configs.error_codes import ErrorCode
from app.configs.errors import GrafanaError
from app.domain.dashboard_model import Dashboard
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.panels_unit_ios_model import PanelsUnitIOs
from app.domain.unit_io_model import UnitIO
from app.domain.unit_model import Unit
from app.dto.enum import (
    AgentType,
    DashboardStatus,
    NotFoundEntity,
    OwnershipType,
)
from app.repositories.dashboard_panel_repository import (
    DashboardPanelRepository,
)
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.grafana_repository import GrafanaRepository
from app.repositories.panels_unit_ios_repository import (
    PanelsUnitIOsRepository,
)
from app.repositories.unit_io_repository import UnitIORepository
from app.repositories.unit_repository import UnitRepository
from app.schemas.pydantic.grafana import (
    DashboardCreate,
    DashboardFilter,
    DashboardPanelCreate,
    DashboardPanelsResult,
    DatasourceFilter,
    DatasourceTimeSeriesData,
    LinkUnitIOToPanel,
    UnitIOForPanel,
)
from app.schemas.pydantic.shared import UnitIORead
from app.schemas.pydantic.unit_io import (
    DataPipeFilter,
)
from app.services.access_service import AccessService
from app.services.unit_io_service import UnitIOService
from app.services.user_service import UserService
from app.services.validators import is_valid_object, is_valid_string_with_rules
from app.validators.data_pipe import is_valid_data_pipe_config


class GrafanaService:
    def __init__(
        self,
        dashboard_repository: DashboardRepository = Depends(),
        dashboard_panel_repository: DashboardPanelRepository = Depends(),
        panels_unit_ios_repository: PanelsUnitIOsRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        unit_io_repository: UnitIORepository = Depends(),
        data_pipe_repository: DataPipeRepository = Depends(),
        access_service: AccessService = Depends(),
        user_service: UserService = Depends(),
        unit_io_service: UnitIOService = Depends(),
    ) -> None:
        self.dashboard_repository = dashboard_repository
        self.dashboard_panel_repository = dashboard_panel_repository
        self.panels_unit_ios_repository = panels_unit_ios_repository
        self.unit_repository = unit_repository
        self.unit_io_repository = unit_io_repository
        self.data_pipe_repository = data_pipe_repository
        self.grafana_repository = GrafanaRepository(data_pipe_repository)
        self.access_service = access_service
        self.user_service = user_service
        self.unit_io_service = unit_io_service

    def get_datasource_data(
        self, filters: DatasourceFilter
    ) -> list[DatasourceTimeSeriesData]:
        self.access_service.authorization.check_access(
            [AgentType.GRAFANA_UNIT_IO]
        )

        unit_io = self.unit_io_repository.get(
            UnitIO(uuid=self.access_service.current_agent.uuid)
        )
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)

        unit_io_panel = self.panels_unit_ios_repository.get_by_parent(
            unit_io,
            DashboardPanel(uuid=self.access_service.current_agent.panel_uuid),
        )
        is_valid_object(unit_io_panel, NotFoundEntity.PANELS_UNIT_IOS)

        self.unit_io_service.is_valid_active_data_pipe(unit_io)
        data_pipe_entity = is_valid_data_pipe_config(
            json.loads(unit_io.data_pipe_yml), is_business_validator=True
        )

        return self.grafana_repository.get_datasource_data(
            DataPipeFilter(
                uuid=self.access_service.current_agent.uuid,
                type=data_pipe_entity.processing_policy.policy_type,
                start_agg_window_datetime=filters.start_agg_datetime,
                end_agg_window_datetime=filters.end_agg_datetime,
                relative_time=filters.relative_time,
                order_by_create_date=filters.order_by_create_date,
                offset=filters.offset,
                limit=filters.limit,
            ),
            data_pipe_entity,
            unit_io_panel,
        )

    def create_dashboard(self, data: DashboardCreate) -> Dashboard:
        self.access_service.authorization.check_access([AgentType.USER])

        if not is_valid_string_with_rules(data.name):
            msg = "Name is not correct"
            raise GrafanaError(msg, code=ErrorCode.GRAFANA_NAME_INVALID)

        dashboard = Dashboard(
            name=data.name,
            create_datetime=datetime.datetime.now(datetime.UTC),
            creator_uuid=self.access_service.current_agent.uuid,
        )

        return self.dashboard_repository.create(dashboard)

    def create_dashboard_panel(
        self, data: DashboardPanelCreate
    ) -> DashboardPanel:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(
            Dashboard(uuid=data.dashboard_uuid)
        )
        is_valid_object(dashboard, NotFoundEntity.DASHBOARD)
        self.access_service.authorization.check_ownership(
            dashboard, [OwnershipType.CREATOR]
        )

        if not is_valid_string_with_rules(data.title):
            msg = "Title is not correct"
            raise GrafanaError(msg, code=ErrorCode.GRAFANA_TITLE_INVALID)

        dashboard_panel = DashboardPanel(
            title=data.title,
            type=data.type,
            create_datetime=datetime.datetime.now(datetime.UTC),
            creator_uuid=self.access_service.current_agent.uuid,
            dashboard_uuid=data.dashboard_uuid,
        )

        return self.dashboard_panel_repository.create(dashboard_panel)

    def link_unit_io_to_panel(self, data: LinkUnitIOToPanel) -> UnitIOForPanel:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=data.unit_io_uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)
        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR]
        )

        dashboard_panel = self.dashboard_panel_repository.get(
            DashboardPanel(uuid=data.dashboard_panels_uuid)
        )
        is_valid_object(dashboard_panel, NotFoundEntity.DASHBOARD_PANEL)
        self.access_service.authorization.check_ownership(
            dashboard_panel, [OwnershipType.CREATOR]
        )

        self.check_unique_unit_io_for_panel(dashboard_panel, unit_io)
        self.is_valid_unit_io_in_panel_count(dashboard_panel.uuid)

        panel_unit_io = PanelsUnitIOs(
            is_last_data=data.is_last_data,
            is_forced_to_json=data.is_forced_to_json,
            create_datetime=datetime.datetime.now(datetime.UTC),
            creator_uuid=self.access_service.current_agent.uuid,
            unit_io_uuid=data.unit_io_uuid,
            dashboard_panels_uuid=data.dashboard_panels_uuid,
        )

        panel_unit_io = self.panels_unit_ios_repository.create(panel_unit_io)

        unit = self.unit_repository.get(Unit(uuid=unit_io.unit_uuid))

        return UnitIOForPanel(
            unit_io=UnitIORead(**unit_io.dict()),
            is_last_data=panel_unit_io.is_last_data,
            is_forced_to_json=panel_unit_io.is_forced_to_json,
            unit_with_unit_io_name=unit.name + "@" + unit_io.topic_name,
        )

    def get_dashboard(self, uuid: uuid_pkg.UUID) -> Dashboard:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard, NotFoundEntity.DASHBOARD)
        self.access_service.authorization.check_ownership(
            dashboard, [OwnershipType.CREATOR]
        )

        return dashboard

    def list_dashboards(
        self, filters: DashboardFilter
    ) -> tuple[int, list[Dashboard]]:
        self.access_service.authorization.check_access([AgentType.USER])

        count, dashboards = self.dashboard_repository.list(
            filters=filters,
            creator_uuid=self.access_service.current_agent.uuid,
        )

        return count, dashboards

    def get_dashboard_panels(
        self, uuid: uuid_pkg.UUID
    ) -> DashboardPanelsResult:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard, NotFoundEntity.DASHBOARD)
        self.access_service.authorization.check_ownership(
            dashboard, [OwnershipType.CREATOR]
        )

        count, panels = self.dashboard_repository.get_dashboard_panels(uuid)
        return DashboardPanelsResult(count=count, panels=panels)

    async def sync_dashboard(self, uuid: uuid_pkg.UUID) -> Dashboard:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard, NotFoundEntity.DASHBOARD)
        self.access_service.authorization.check_ownership(
            dashboard, [OwnershipType.CREATOR]
        )

        count, panels = self.dashboard_repository.get_dashboard_panels(uuid)
        dashboard_dict = await self.grafana_repository.generate_dashboard(
            dashboard, panels
        )

        dashboard.sync_status = DashboardStatus.PROCESSING
        dashboard.sync_error = None
        dashboard.sync_last_datetime = datetime.datetime.now(datetime.UTC)

        self.user_service.create_org_if_not_exists(
            self.access_service.current_agent.uuid
        )

        try:
            sync_result = self.grafana_repository.sync_dashboard(
                self.access_service.current_agent.grafana_org_id,
                dashboard_dict,
            )
            dashboard.dashboard_url = sync_result["url"]
            dashboard.inc_last_version = sync_result["version"]
            dashboard.sync_status = DashboardStatus.SUCCESS
            dashboard.sync_error = None
        except Exception as e:
            dashboard.sync_status = DashboardStatus.ERROR
            dashboard.sync_error = str(e)

        return self.dashboard_repository.update(dashboard.uuid, dashboard)

    def delete_dashboard(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard, NotFoundEntity.DASHBOARD)

        self.access_service.authorization.check_ownership(
            dashboard, [OwnershipType.CREATOR]
        )

        self.dashboard_repository.delete(dashboard)

    def delete_panel(self, uuid: uuid_pkg.UUID) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard_panel = self.dashboard_panel_repository.get(
            DashboardPanel(uuid=uuid)
        )
        is_valid_object(dashboard_panel, NotFoundEntity.DASHBOARD_PANEL)

        self.access_service.authorization.check_ownership(
            dashboard_panel, [OwnershipType.CREATOR]
        )

        self.dashboard_panel_repository.delete(dashboard_panel)

    def delete_link(
        self,
        unit_io_uuid: uuid_pkg.UUID,
        dashboard_panel_uuid: uuid_pkg.UUID,
    ) -> None:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_io = self.unit_io_repository.get(UnitIO(uuid=unit_io_uuid))
        is_valid_object(unit_io, NotFoundEntity.UNIT_IO)
        self.access_service.authorization.check_ownership(
            unit_io, [OwnershipType.CREATOR]
        )

        dashboard_panel = self.dashboard_panel_repository.get(
            DashboardPanel(uuid=dashboard_panel_uuid)
        )
        is_valid_object(dashboard_panel, NotFoundEntity.DASHBOARD_PANEL)
        self.access_service.authorization.check_ownership(
            dashboard_panel, [OwnershipType.CREATOR]
        )

        self.panels_unit_ios_repository.delete(unit_io, dashboard_panel)

    def check_unique_unit_io_for_panel(
        self, dashboard_panel: Dashboard, unit_io: UnitIO
    ):
        if self.dashboard_panel_repository.check_unique_unit_io_for_panel(
            dashboard_panel, unit_io
        ):
            msg = "This UnitIO is not unique for this Panel"
            raise GrafanaError(msg, code=ErrorCode.GRAFANA_UNIT_IO_NOT_UNIQUE)

    def is_valid_unit_io_in_panel_count(self, uuid: uuid_pkg.UUID):
        limit = runtime.get().pu_datapipe_limit_unit_io_per_one_panel
        if (
            self.dashboard_panel_repository.get_count_unit_for_panel(uuid)
            >= limit
        ):
            msg = f"Limit UnitIO for one panel is {limit}"
            raise GrafanaError(msg, code=ErrorCode.GRAFANA_PANEL_UNIT_IO_LIMIT)
