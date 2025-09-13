import uuid as uuid_pkg
from collections import defaultdict
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
from app.schemas.pydantic.grafana import DashboardFilter, DashboardPanelRead, UnitNodeForPanel
from app.schemas.pydantic.shared import UnitNodeRead


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

    def get_dashboard_panels(self, uuid: uuid_pkg.UUID) -> tuple[int, List[DashboardPanelRead]]:

        query = (
            self.db.query(DashboardPanel, PanelsUnitNodes, UnitNode, Unit)
            .outerjoin(PanelsUnitNodes, DashboardPanel.uuid == PanelsUnitNodes.dashboard_panels_uuid, full=True)
            .outerjoin(UnitNode, PanelsUnitNodes.unit_node_uuid == UnitNode.uuid, full=True)
            .outerjoin(Unit, UnitNode.unit_uuid == Unit.uuid, full=True)
            .filter(DashboardPanel.dashboard_uuid == uuid)
            .all()
        )

        panels_dict: dict[uuid_pkg.UUID, dict] = defaultdict(lambda: {"panel": None, "unit_nodes": []})

        for panel, panel_unit_node, unit_node, unit in query:
            if panels_dict[panel.uuid]["panel"] is None:
                panels_dict[panel.uuid]["panel"] = panel

            if unit_node:
                panels_dict[panel.uuid]["unit_nodes"].append(
                    UnitNodeForPanel(
                        unit_node=UnitNodeRead(**unit_node.dict()),
                        is_last_data=panel_unit_node.is_last_data,
                        is_forced_to_json=panel_unit_node.is_forced_to_json,
                        unit_with_unit_node_name=f"{unit.name}@{unit_node.topic_name}",
                    )
                )

        panels = []
        for panel_uuid, data in panels_dict.items():
            panel = data["panel"]
            panels.append(
                DashboardPanelRead(
                    uuid=panel.uuid,
                    type=panel.type,
                    title=panel.title,
                    create_datetime=panel.create_datetime,
                    creator_uuid=panel.creator_uuid,
                    dashboard_uuid=panel.dashboard_uuid,
                    unit_nodes_for_panel=data["unit_nodes"],
                )
            )

        return len(panels), panels
