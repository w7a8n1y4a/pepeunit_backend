import uuid as uuid_pkg
from typing import List, Optional

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.dashboard_model import Dashboard
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_ilike_search_string, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.grafana import DashboardFilter, DashboardPanelsRead, UnitNodeForPanel


class DashboardRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Dashboard, db)

    def list(
        self, filters: DashboardFilter, creator_uuid: Optional[uuid_pkg.UUID] = None
    ) -> tuple[int, list[Dashboard]]:
        query = self.db.query(Dashboard)

        if creator_uuid:
            query = query.filter(Dashboard.creator_uuid == creator_uuid)

        fields = [Dashboard.name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {
            'order_by_create_date': Dashboard.create_datetime,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def get_dashboard_panels(self, uuid: uuid_pkg.UUID) -> tuple[int, List[DashboardPanelsRead]]:

        query = (
            self.db.query(Dashboard)
            .join(DashboardPanel, Dashboard.uuid == DashboardPanel.dashboard_uuid)
            .join(PanelsUnitNodes, DashboardPanel.uuid == PanelsUnitNodes.dashboard_panels_uuid)
            .join(UnitNode, PanelsUnitNodes.unit_node_uuid == UnitNode.uuid)
            .join(Unit, UnitNode.unit_uuid == Unit.uuid)
            .filter(Dashboard.uuid == uuid)
            .all()
        )

        return len(query), [
            DashboardPanelsRead(
                uuid=panel.uuid,
                type=panel.type,
                title=panel.title,
                create_datetime=panel.create_datetime,
                creator_uuid=panel.creator_uuid,
                dashboard_uuid=panel.dashboard_uuid,
                unit_nodes_for_panel=[
                    UnitNodeForPanel(
                        unit_node=un,
                        is_last_data=un.is_last_data,
                        unit_with_unit_node_name=f"{un.unit.name} - {un.name}",
                    )
                    for un in [pun.unit_node for pun in panel.panels_unit_nodes]
                ],
            )
            for panel in query
        ]
