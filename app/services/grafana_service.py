import datetime
import json
import uuid as uuid_pkg
from typing import Union

from fastapi import Depends

from app.configs.errors import GrafanaError
from app.domain.dashboard_model import Dashboard
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.domain.unit_node_model import UnitNode
from app.dto.enum import (
    AgentType,
    OwnershipType,
)
from app.repositories.dashboard_panel_repository import DashboardPanelRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.grafana_repository import GrafanaRepository
from app.repositories.panels_unit_nodes_repository import PanelsUnitNodesRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.schemas.pydantic.grafana import (
    DashboardCreate,
    DashboardFilter,
    DashboardPanelCreate,
    DashboardPanelsResult,
    DatasourceFilter,
    DatasourceTimeseries,
    LinkUnitNodeToPanel,
)
from app.schemas.pydantic.unit_node import (
    DataPipeFilter,
)
from app.services.access_service import AccessService
from app.services.unit_node_service import UnitNodeService
from app.services.validators import is_valid_object, is_valid_string_with_rules
from app.validators.data_pipe import is_valid_data_pipe_config


class GrafanaService:
    def __init__(
        self,
        dashboard_repository: DashboardRepository = Depends(),
        dashboard_panel_repository: DashboardPanelRepository = Depends(),
        panels_unit_nodes_repository: PanelsUnitNodesRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        data_pipe_repository: DataPipeRepository = Depends(),
        access_service: AccessService = Depends(),
        unit_node_service: UnitNodeService = Depends(),
    ) -> None:
        self.dashboard_repository = dashboard_repository
        self.dashboard_panel_repository = dashboard_panel_repository
        self.panels_unit_nodes_repository = panels_unit_nodes_repository
        self.grafana_repository = GrafanaRepository()
        self.unit_node_repository = unit_node_repository
        self.data_pipe_repository = data_pipe_repository
        self.access_service = access_service
        self.unit_node_service = unit_node_service

    def get_datasource_data(self, filters: DatasourceFilter) -> list[DatasourceTimeseries]:
        self.access_service.authorization.check_access([AgentType.GRAFANA_UNIT_NODE])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=self.access_service.current_agent.uuid))
        is_valid_object(unit_node)

        self.unit_node_service.is_valid_active_data_pipe(unit_node)
        data_pipe_entity = is_valid_data_pipe_config(json.loads(unit_node.data_pipe_yml), is_business_validator=True)

        count, data = self.data_pipe_repository.list(
            DataPipeFilter(
                uuid=self.access_service.current_agent.uuid,
                type=data_pipe_entity.processing_policy.policy_type,
                start_agg_window_datetime=filters.start_agg_datetime,
                end_agg_window_datetime=filters.end_agg_datetime,
                relative_time=filters.relative_time,
                order_by_create_date=filters.order_by_create_date,
                offset=filters.offset,
                limit=filters.limit,
            )
        )

        return [
            DatasourceTimeseries(time=int(item.end_window_datetime.timestamp() * 1000), value=item.state)
            for item in data
        ]

    def create_dashboard(self, data: Union[DashboardCreate]) -> Dashboard:
        self.access_service.authorization.check_access([AgentType.USER])

        if not is_valid_string_with_rules(data.name):
            raise GrafanaError('Name is not correct')

        dashboard = Dashboard(
            name=data.name,
            create_datetime=datetime.datetime.utcnow(),
            creator_uuid=self.access_service.current_agent.uuid,
        )

        return self.dashboard_repository.create(dashboard)

    def create_dashboard_panel(self, data: Union[DashboardPanelCreate]) -> DashboardPanel:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=data.dashboard_uuid))
        is_valid_object(dashboard)
        self.access_service.authorization.check_ownership(dashboard, [OwnershipType.CREATOR])

        if not is_valid_string_with_rules(data.title):
            raise GrafanaError('Title is not correct')

        dashboard_panel = DashboardPanel(
            title=data.title,
            type=data.type,
            create_datetime=datetime.datetime.utcnow(),
            creator_uuid=self.access_service.current_agent.uuid,
            dashboard_uuid=data.dashboard_uuid,
        )

        return self.dashboard_panel_repository.create(dashboard_panel)

    def link_unit_node_to_panel(self, data: Union[LinkUnitNodeToPanel]) -> PanelsUnitNodes:
        self.access_service.authorization.check_access([AgentType.USER])

        unit_node = self.unit_node_repository.get(UnitNode(uuid=data.unit_node_uuid))
        is_valid_object(unit_node)
        self.access_service.authorization.check_ownership(unit_node, [OwnershipType.CREATOR])

        dashboard_panel = self.dashboard_panel_repository.get(DashboardPanel(uuid=data.dashboard_panels_uuid))
        is_valid_object(dashboard_panel)
        self.access_service.authorization.check_ownership(dashboard_panel, [OwnershipType.CREATOR])

        # TODO: проверка лимита числа unit_node для одной панели
        # TODO: добавить валидацию что unit_node подходит своим DataPipe для текущей панели

        panel_unit_node = PanelsUnitNodes(
            is_last_data=data.is_last_data,
            create_datetime=datetime.datetime.utcnow(),
            creator_uuid=self.access_service.current_agent.uuid,
            unit_node_uuid=data.unit_node_uuid,
            dashboard_panels_uuid=data.dashboard_panels_uuid,
        )

        return self.panels_unit_nodes_repository.create(panel_unit_node)

    def get_dashboard(self, uuid: uuid_pkg.UUID) -> Dashboard:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard)
        self.access_service.authorization.check_ownership(dashboard, [OwnershipType.CREATOR])

        return dashboard

    def list_dashboards(self, uuid: uuid_pkg.UUID, filters: Union[DashboardFilter]) -> tuple[int, list[Dashboard]]:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard)
        self.access_service.authorization.check_ownership(dashboard, [OwnershipType.CREATOR])

        count, dashboards = self.dashboard_repository.list(
            filters=filters,
            creator_uuid=self.access_service.current_agent.uuid,
        )

        return count, dashboards

    def get_dashboard_panels(self, uuid: uuid_pkg.UUID) -> DashboardPanelsResult:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard)
        self.access_service.authorization.check_ownership(dashboard, [OwnershipType.CREATOR])

        count, panels = self.dashboard_repository.get_dashboard_panels(uuid)
        return DashboardPanelsResult(count=count, panels=panels)

    def sync_dashboard(self, uuid: uuid_pkg.UUID) -> Dashboard:
        self.access_service.authorization.check_access([AgentType.USER])

        dashboard = self.dashboard_repository.get(Dashboard(uuid=uuid))
        is_valid_object(dashboard)
        self.access_service.authorization.check_ownership(dashboard, [OwnershipType.CREATOR])

        count, panels = self.dashboard_repository.get_dashboard_panels(uuid)
        dashboard_dict = self.grafana_repository.generate_dashboard(dashboard, panels)
        self.grafana_repository.sync_dashboard(self.access_service.current_agent.grafana_org_id, dashboard_dict)

        # TODO: автоматический подбор типа таргета в панели, на основе DataPipe

        # TODO: Сохранение результатов запроса в dashboard
        # TODO: Отдать с уже обновлёнными статусами
