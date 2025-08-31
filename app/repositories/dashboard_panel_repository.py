from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.dashboard_panel_model import DashboardPanel
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
