from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.panels_unit_nodes_model import PanelsUnitNodes
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.grafana import PanelsUnitNodesFilter
from app.services.validators import is_valid_uuid


class PanelsUnitNodesRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(PanelsUnitNodes, db)

    def list(self, filters: PanelsUnitNodesFilter) -> tuple[int, list[PanelsUnitNodes]]:
        query = self.db.query(PanelsUnitNodes)

        if filters.unit_node_uuid:
            query = query.filter(PanelsUnitNodes.unit_node_uuid == is_valid_uuid(filters.unit_node_uuid))

        if filters.dashboard_panels_uuid:
            query = query.filter(PanelsUnitNodes.dashboard_panels_uuid == is_valid_uuid(filters.dashboard_panels_uuid))

        fields = {
            'order_by_create_date': PanelsUnitNodes.create_datetime,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()
