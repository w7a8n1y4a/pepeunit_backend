from typing import Optional

from fastapi import Depends
from fastapi_filter.contrib.sqlalchemy import Filter
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.repositories.enum import VisibilityLevel, OrderByDate
from app.domain.unit_model import Unit
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by


class UnitFilter(Filter):
    """Фильтр выборки Unit"""

    search_string: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


class UnitRepository:
    db: Session

    def __init__(
        self, db: Session = Depends(get_session)
    ) -> None:
        self.db = db

    def create(self, unit: Unit) -> Unit:
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def get(self, unit: Unit) -> Unit:
        return self.db.get(Unit, unit.uuid)

    def update(self, uuid, unit: Unit) -> Unit:
        unit.uuid = uuid
        self.db.merge(unit)
        self.db.commit()
        return unit

    def delete(self, unit: Unit) -> None:
        self.db.delete(unit)
        self.db.commit()
        self.db.flush()

    def list(self, filters: UnitFilter) -> list[Unit]:
        query = self.db.query(Unit)

        fields = [Unit.name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {UnitFilter.visibility_level: Unit.visibility_level}
        query = apply_enums(query, filters, fields)

        query = apply_offset_and_limit(query, filters)

        fields = {
            UnitFilter.order_by_create_date: Unit.create_datetime,
            UnitFilter.order_by_last_update: Unit.last_update_datetime
        }
        query = apply_orders_by(query, filters, fields)

        return query.all()
