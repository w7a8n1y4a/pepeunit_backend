import uuid as uuid_pkg

from fastapi import Depends
from fastapi.params import Query
from sqlalchemy import func, text
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from app.configs.db import get_session
from app.configs.error_codes import ErrorCode
from app.configs.errors import UnitError
from app.domain.link_model import Link
from app.domain.unit_group_unit_model import UnitGroupUnit
from app.domain.unit_io_model import UnitIO
from app.domain.unit_model import Unit
from app.dto.enum import UuidEntity, VisibilityLevel
from app.repositories.base_repository import BaseRepository, UniqueNameMixin
from app.repositories.utils import (
    apply_enums,
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
    apply_restriction,
)
from app.schemas.pydantic.unit import UnitFilter
from app.schemas.pydantic.unit_group import UnitGroupMemberFilter
from app.services.validators import is_valid_string_with_rules, is_valid_uuid


class UnitRepository(UniqueNameMixin, BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(Unit, db)

    def list(
        self,
        filters: UnitFilter,
        restriction: list[str] = None,
        is_include_output_unit_ios: bool = False,
    ) -> tuple[int, list[tuple[Unit, list[dict]]]]:
        link_alias = aliased(Link)
        unit_io_alias = aliased(UnitIO, name="unit_io_alias")

        if is_include_output_unit_ios:
            if filters.unit_io_input_uuid:
                unit_io_by_input_subquery = (
                    self.db.query(
                        func.json_agg(text("unit_io_alias")).label("unit_ios")
                    )
                    .select_from(unit_io_alias)
                    .join(
                        link_alias,
                        link_alias.output_uuid == unit_io_alias.uuid,
                    )
                    .filter(
                        link_alias.input_uuid
                        == is_valid_uuid(
                            filters.unit_io_input_uuid,
                            UuidEntity.UNIT_IO_INPUT,
                        ),
                        unit_io_alias.unit_uuid == Unit.uuid,
                    )
                )

                query = (
                    self.db.query(
                        Unit, unit_io_by_input_subquery.label("output_nodes")
                    )
                    .select_from(Unit)
                    .join(UnitIO, Unit.uuid == UnitIO.unit_uuid)
                    .join(
                        Link,
                        UnitIO.uuid == Link.output_uuid,
                    )
                    .filter(
                        Link.input_uuid
                        == is_valid_uuid(
                            filters.unit_io_input_uuid,
                            UuidEntity.UNIT_IO_INPUT,
                        )
                    )
                    .group_by(Unit.uuid)
                )
            else:
                unit_io_subquery = (
                    self.db.query(
                        func.json_agg(text("unit_io_alias")).label("unit_ios")
                    )
                    .select_from(unit_io_alias)
                    .filter(
                        unit_io_alias.type.in_(filters.unit_io_type),
                        unit_io_alias.unit_uuid == Unit.uuid,
                    )
                )

                if filters.unit_io_uuids:
                    unit_io_subquery = unit_io_subquery.filter(
                        unit_io_alias.uuid.in_(filters.unit_io_uuids)
                    )

                query = (
                    self.db.query(Unit, unit_io_subquery.label("output_nodes"))
                    .select_from(Unit)
                    .join(UnitIO, Unit.uuid == UnitIO.unit_uuid)
                    .group_by(Unit.uuid)
                )

                if filters.unit_io_uuids:
                    query = query.filter(
                        UnitIO.uuid.in_(filters.unit_io_uuids)
                    )

        else:
            query = self.db.query(Unit)

        filters.uuids = (
            filters.uuids.default
            if isinstance(filters.uuids, Query)
            else filters.uuids
        )
        if filters.uuids:
            query = query.filter(
                Unit.uuid.in_(
                    [
                        is_valid_uuid(item, UuidEntity.UNIT)
                        for item in filters.uuids
                    ]
                )
            )

        if filters.creator_uuid:
            query = query.filter(
                Unit.creator_uuid
                == is_valid_uuid(filters.creator_uuid, UuidEntity.USER)
            )
        if filters.repo_uuid:
            query = query.filter(
                Unit.repo_uuid
                == is_valid_uuid(
                    filters.repo_uuid,
                    UuidEntity.REPO,
                )
            )
        if filters.is_auto_update_unit is not None:
            query = query.filter(
                Unit.is_auto_update_unit == filters.is_auto_update_unit
            )

        fields = [Unit.name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {"visibility_level": Unit.visibility_level}
        query = apply_enums(query, filters, fields)

        query = apply_restriction(query, filters, Unit, restriction)

        fields = {
            "order_by_create_date": Unit.create_datetime,
            "order_by_last_update": Unit.last_update_datetime,
            "order_by_unit_name": Unit.name,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)

        return count, (
            [(item[0], item[1] if item[1] else []) for item in query.all()]
            if is_include_output_unit_ios
            else [(item, []) for item in query.all()]
        )

    def list_for_group(
        self, group_uuid: uuid_pkg.UUID, filters: UnitGroupMemberFilter
    ) -> tuple[int, list[Unit]]:
        query = (
            self.db.query(Unit)
            .join(UnitGroupUnit, UnitGroupUnit.unit_uuid == Unit.uuid)
            .filter(UnitGroupUnit.unit_group_uuid == group_uuid)
        )

        query = apply_ilike_search_string(query, filters, [Unit.name])

        fields = {"order_by_unit_name": Unit.name}
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def is_valid_name(self, name: str):
        if not is_valid_string_with_rules(name):
            msg = "Name is not correct"
            raise UnitError(msg, code=ErrorCode.UNIT_NAME_INVALID)

    def get_public_count(self) -> int:
        return self.db.exec(
            select(func.count())
            .select_from(Unit)
            .where(Unit.visibility_level == VisibilityLevel.PUBLIC.value)
        ).one()
