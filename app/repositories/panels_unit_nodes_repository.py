from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.dashboard_panel_model import DashboardPanel
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.domain.unit_node_model import UnitNode
from app.repositories.base_repository import BaseRepository


class PanelsUnitNodesRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(PanelsUnitNodes, db)

    def delete(self, unit_node: UnitNode, dashboard_panel: DashboardPanel) -> None:
        (
            self.db.query(PanelsUnitNodes)
            .filter(
                PanelsUnitNodes.unit_node_uuid == unit_node.uuid,
                PanelsUnitNodes.dashboard_panels_uuid == dashboard_panel.uuid,
            )
            .delete()
        )
        self.db.commit()
        self.db.flush()

    def get_by_parent(
        self, unit_node: UnitNode, dashboard_panel: DashboardPanel
    ) -> PanelsUnitNodes:
        return (
            self.db.query(PanelsUnitNodes)
            .filter(
                PanelsUnitNodes.unit_node_uuid == unit_node.uuid,
                PanelsUnitNodes.dashboard_panels_uuid == dashboard_panel.uuid,
            )
            .first()
        )
