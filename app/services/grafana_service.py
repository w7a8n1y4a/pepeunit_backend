import json

from fastapi import Depends

from app.domain.unit_node_model import UnitNode
from app.dto.enum import (
    AgentType,
)
from app.repositories.dashboard_panel_repository import DashboardPanelRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.data_pipe_repository import DataPipeRepository
from app.repositories.panels_unit_nodes_repository import PanelsUnitNodesRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.schemas.pydantic.grafana import DatasourceFilter, DatasourceTimeseries
from app.schemas.pydantic.unit_node import (
    DataPipeFilter,
)
from app.services.access_service import AccessService
from app.services.unit_node_service import UnitNodeService
from app.services.validators import is_valid_object
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
