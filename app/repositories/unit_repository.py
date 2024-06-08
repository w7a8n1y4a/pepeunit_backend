from fastapi import Depends
from fastapi import HTTPException
from fastapi import status as http_status
from sqlmodel import Session, select

from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.unit import UnitFilter


class UnitRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, unit: Unit) -> Unit:
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def get(self, unit: Unit) -> Unit:
        return self.db.get(Unit, unit.uuid)

    def get_all_count(self) -> int:
        return self.db.query(Unit.uuid).count()

    def update(self, uuid, unit: Unit) -> Unit:
        unit.uuid = uuid
        self.db.merge(unit)
        self.db.commit()
        return self.get(unit)

    def delete(self, unit: Unit) -> None:
        self.db.delete(self.get(unit))
        self.db.commit()
        self.db.flush()

    def list(self, filters: UnitFilter, restriction: list[str] = None) -> list[Unit]:
        query = self.db.query(Unit)

        if filters.creator_uuid:
            query = query.filter(Unit.creator_uuid == filters.creator_uuid)
        if filters.repo_uuid:
            query = query.filter(Unit.repo_uuid == filters.repo_uuid)
        if filters.is_auto_update_from_repo_unit is not None:
            query = query.filter(Unit.is_auto_update_from_repo_unit == filters.is_auto_update_from_repo_unit)
        if restriction:
            query = query.filter(Unit.uuid.in_(restriction))

        fields = [Unit.name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': Unit.visibility_level}
        query = apply_enums(query, filters, fields)

        fields = {'order_by_create_date': Unit.create_datetime, 'order_by_last_update': Unit.last_update_datetime}
        query = apply_orders_by(query, filters, fields)

        query = apply_offset_and_limit(query, filters)
        return query.all()

    def is_valid_name(self, name: str, uuid: str = None):
        repo_uuid = self.db.exec(select(Unit.uuid).where(Unit.name == name)).first()
        repo_uuid = str(repo_uuid) if repo_uuid else repo_uuid

        if (uuid is None and repo_uuid) or (uuid and repo_uuid != uuid and repo_uuid is not None):
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Name is not unique")
