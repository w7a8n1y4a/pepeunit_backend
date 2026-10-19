import uuid as uuid_pkg

from fastapi import Depends
from fastapi.params import Query
from sqlmodel import Session

from app.configs.db import get_session
from app.configs.errors import UnitGroupError
from app.domain.unit_group_model import UnitGroup
from app.domain.unit_group_unit_model import UnitGroupUnit
from app.repositories.base_repository import BaseRepository, UniqueNameMixin
from app.repositories.utils import (
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
)
from app.schemas.pydantic.unit_group import UnitGroupFilter
from app.services.validators import is_valid_string_with_rules, is_valid_uuid


class UnitGroupRepository(UniqueNameMixin, BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(UnitGroup, db)

    def list(
        self, filters: UnitGroupFilter, creator_uuid: uuid_pkg.UUID
    ) -> tuple[int, list[UnitGroup]]:
        query = self.db.query(UnitGroup).filter(
            UnitGroup.creator_uuid == creator_uuid
        )

        if filters.unit_uuid:
            query = query.join(
                UnitGroupUnit,
                UnitGroupUnit.unit_group_uuid == UnitGroup.uuid,
            ).filter(
                UnitGroupUnit.unit_uuid == is_valid_uuid(filters.unit_uuid)
            )

        filters.uuids = (
            filters.uuids.default
            if isinstance(filters.uuids, Query)
            else filters.uuids
        )
        if filters.uuids:
            query = query.filter(
                UnitGroup.uuid.in_(
                    [is_valid_uuid(item) for item in filters.uuids]
                )
            )

        query = apply_ilike_search_string(query, filters, [UnitGroup.name])

        fields = {
            "order_by_create_date": UnitGroup.create_datetime,
            "order_by_group_name": UnitGroup.name,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def count_by_creator(self, creator_uuid: uuid_pkg.UUID) -> int:
        return (
            self.db.query(UnitGroup)
            .filter(UnitGroup.creator_uuid == creator_uuid)
            .count()
        )

    def is_valid_name(self, name: str):
        if not is_valid_string_with_rules(name):
            msg = "Name is not correct"
            raise UnitGroupError(msg)
