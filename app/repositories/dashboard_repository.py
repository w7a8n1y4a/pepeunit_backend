import uuid as uuid_pkg
from typing import Optional

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.dashboard_model import Dashboard
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_ilike_search_string, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.grafana import DashboardFilter, DashboardPanelsResult


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

    def get_dashboard_panels(self, uuid: uuid_pkg.UUID) -> DashboardPanelsResult:

        query = self.db.query(Dashboard)
