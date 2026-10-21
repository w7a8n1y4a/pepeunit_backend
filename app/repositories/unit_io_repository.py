import uuid as uuid_pkg

from fastapi import Depends
from fastapi.params import Query
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from app.configs.db import get_session
from app.domain.link_model import Link
from app.domain.unit_io_model import UnitIO
from app.dto.enum import UuidEntity, VisibilityLevel
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import (
    apply_enums,
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
    apply_restriction,
)
from app.schemas.pydantic.unit_io import UnitIOFilter
from app.services.validators import is_valid_uuid


class UnitIORepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(UnitIO, db)

    def bulk_save(self, unit_ios: list[UnitIO]) -> None:
        self.db.bulk_save_objects(unit_ios)
        self.db.commit()

    def get_by_topic(
        self, unit_uuid: uuid_pkg.UUID, unit_io: UnitIO
    ) -> UnitIO:
        return (
            self.db.query(UnitIO)
            .filter(
                UnitIO.unit_uuid == unit_uuid,
                UnitIO.topic_name == unit_io.topic_name,
                UnitIO.type == unit_io.type,
            )
            .first()
        )

    def get_nodes_with_links(self, unit_uuid: uuid_pkg.UUID) -> list[tuple]:
        link_alias = aliased(Link)
        unit_io_alias = aliased(UnitIO)

        link_subquery = (
            self.db.query(
                func.json_agg(
                    func.json_build_array(
                        link_alias.output_uuid,
                        unit_io_alias.topic_name,
                    )
                ).label("test")
            )
            .select_from(link_alias)
            .join(
                unit_io_alias,
                link_alias.output_uuid == unit_io_alias.uuid,
            )
            .filter(link_alias.input_uuid == UnitIO.uuid)
        )

        return (
            self.db.query(
                UnitIO.uuid,
                UnitIO.topic_name,
                UnitIO.type,
                link_subquery.label("links"),
            )
            .select_from(Link)
            .outerjoin(
                UnitIO,
                Link.input_uuid == UnitIO.uuid,
                full=True,
            )
            .filter(UnitIO.unit_uuid == unit_uuid)
            .group_by(UnitIO.uuid, UnitIO.topic_name, UnitIO.type)
            .all()
        )

    def delete(self, del_uuid_list: list[str]) -> None:
        self.db.query(UnitIO).filter(UnitIO.uuid.in_(del_uuid_list)).delete()
        self.db.commit()

    def list(
        self, filters: UnitIOFilter, restriction: list[str] = None
    ) -> tuple[int, list[UnitIO]]:
        query = self.db.query(UnitIO)

        if filters.output_uuid:
            query = query.join(Link, Link.input_uuid == UnitIO.uuid).filter(
                Link.output_uuid == filters.output_uuid
            )

        filters.uuids = (
            filters.uuids.default
            if isinstance(filters.uuids, Query)
            else filters.uuids
        )
        if filters.uuids:
            query = query.filter(
                UnitIO.uuid.in_(
                    [
                        is_valid_uuid(item, UuidEntity.UNIT_IO)
                        for item in filters.uuids
                    ]
                )
            )

        if filters.unit_uuid:
            query = query.filter(
                UnitIO.unit_uuid
                == is_valid_uuid(filters.unit_uuid, UuidEntity.UNIT)
            )

        fields = [UnitIO.topic_name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {
            "visibility_level": UnitIO.visibility_level,
            "type": UnitIO.type,
        }
        query = apply_enums(query, filters, fields)

        query = apply_restriction(query, filters, UnitIO, restriction)

        fields = {"order_by_create_date": UnitIO.create_datetime}
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def get_public_count(self) -> int:
        return self.db.exec(
            select(func.count())
            .select_from(UnitIO)
            .where(UnitIO.visibility_level == VisibilityLevel.PUBLIC.value)
        ).one()
