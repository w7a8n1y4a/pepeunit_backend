import uuid as uuid_pkg

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.dashboard_model import Dashboard
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.domain.unit_node_model import UnitNode
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_ilike_search_string, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.grafana import DashboardPanelFilter
from app.services.validators import is_valid_uuid


class DashboardPanelRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(DashboardPanel, db)

    def list(self, filters: DashboardPanelFilter) -> tuple[int, list[DashboardPanel]]:
        query = self.db.query(DashboardPanel)

        if filters.dashboard_uuid:
            query = query.filter(DashboardPanel.dashboard_uuid == is_valid_uuid(filters.dashboard_uuid))

        fields = [DashboardPanel.title]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {
            'order_by_create_date': DashboardPanel.create_datetime,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def get_count_unit_for_panel(self, uuid: uuid_pkg.UUID) -> int:
        return self.db.query(PanelsUnitNodes).filter(PanelsUnitNodes.dashboard_panels_uuid == uuid).count()

    def check_unique_unit_node_for_panel(self, dashboard_panel: Dashboard, unit_node: UnitNode) -> int:
        return (
            self.db.query(PanelsUnitNodes)
            .filter(
                PanelsUnitNodes.dashboard_panels_uuid == dashboard_panel.uuid,
                PanelsUnitNodes.unit_node_uuid == unit_node.uuid,
            )
            .count()
        )
