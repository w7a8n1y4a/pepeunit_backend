import uuid as uuid_pkg
from typing import Optional

from fastapi import Depends
from fastapi.params import Query
from sqlalchemy import func, text
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.utils import (
    apply_enums,
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
    apply_restriction,
)
from app.schemas.pydantic.unit import UnitFilter
from app.services.validators import is_valid_string_with_rules, is_valid_uuid


class UnitRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, unit: Unit) -> Unit:
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def get(self, unit: Unit) -> Optional[Unit]:
        return self.db.get(Unit, unit.uuid)

    def get_all_count(self) -> int:
        return self.db.query(Unit.uuid).count()

    def update(self, uuid: uuid_pkg.UUID, unit: Unit) -> Unit:
        unit.uuid = uuid
        self.db.merge(unit)
        self.db.commit()
        return self.get(unit)

    def delete(self, unit: Unit) -> None:
        self.db.delete(self.get(unit))
        self.db.commit()
        self.db.flush()

    def list(
        self, filters: UnitFilter, restriction: list[str] = None, is_include_output_unit_nodes: bool = False
    ) -> tuple[int, list[tuple[Unit, list[dict]]]]:

        unit_node_edge_alias = aliased(UnitNodeEdge)
        unit_node_alias = aliased(UnitNode, name="unit_node_alias")

        if is_include_output_unit_nodes:
            if filters.unit_node_input_uuid:
                unit_node_by_input_subquery = (
                    self.db.query(func.json_agg(text('unit_node_alias')).label('unit_nodes'))
                    .select_from(unit_node_alias)
                    .join(unit_node_edge_alias, unit_node_edge_alias.node_output_uuid == unit_node_alias.uuid)
                    .filter(
                        unit_node_edge_alias.node_input_uuid == is_valid_uuid(filters.unit_node_input_uuid),
                        unit_node_alias.unit_uuid == Unit.uuid,
                    )
                )

                query = (
                    self.db.query(Unit, unit_node_by_input_subquery.label('output_nodes'))
                    .select_from(Unit)
                    .join(UnitNode, Unit.uuid == UnitNode.unit_uuid)
                    .join(UnitNodeEdge, UnitNode.uuid == UnitNodeEdge.node_output_uuid)
                    .filter(UnitNodeEdge.node_input_uuid == is_valid_uuid(filters.unit_node_input_uuid))
                    .group_by(Unit.uuid)
                )
            else:
                unit_node_subquery = (
                    self.db.query(func.json_agg(text('unit_node_alias')).label('unit_nodes'))
                    .select_from(unit_node_alias)
                    .filter(
                        unit_node_alias.type.in_(filters.unit_node_type),
                        unit_node_alias.unit_uuid == Unit.uuid,
                    )
                )

                if filters.unit_node_uuids:
                    unit_node_subquery = unit_node_subquery.filter(unit_node_alias.uuid.in_(filters.unit_node_uuids))

                query = (
                    self.db.query(Unit, unit_node_subquery.label('output_nodes'))
                    .select_from(Unit)
                    .join(UnitNode, Unit.uuid == UnitNode.unit_uuid)
                    .group_by(Unit.uuid)
                )

                if filters.unit_node_uuids:
                    query = query.filter(UnitNode.uuid.in_(filters.unit_node_uuids))

        else:
            query = self.db.query(Unit)

        filters.uuids = filters.uuids.default if isinstance(filters.uuids, Query) else filters.uuids
        if filters.uuids:
            query = query.filter(Unit.uuid.in_([is_valid_uuid(item) for item in filters.uuids]))

        if filters.creator_uuid:
            query = query.filter(Unit.creator_uuid == is_valid_uuid(filters.creator_uuid))
        if filters.repo_uuid:
            query = query.filter(Unit.repo_uuid == is_valid_uuid(filters.repo_uuid))

        filters.repos_uuids = (
            filters.repos_uuids.default if isinstance(filters.repos_uuids, Query) else filters.repos_uuids
        )
        if filters.repos_uuids:
            query = query.filter(Unit.repo_uuid.in_([is_valid_uuid(item) for item in filters.repos_uuids]))
        if filters.is_auto_update_from_repo_unit is not None:
            query = query.filter(Unit.is_auto_update_from_repo_unit == filters.is_auto_update_from_repo_unit)

        fields = [Unit.name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': Unit.visibility_level}
        query = apply_enums(query, filters, fields)

        query = apply_restriction(query, filters, Unit, restriction)

        fields = {
            'order_by_create_date': Unit.create_datetime,
            'order_by_last_update': Unit.last_update_datetime,
            'order_by_unit_name': Unit.name,
        }
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)

        return count, (
            [(item[0], item[1] if item[1] else []) for item in query.all()]
            if is_include_output_unit_nodes
            else [(item, []) for item in query.all()]
        )

    def is_valid_name(self, name: str, uuid: Optional[uuid_pkg.UUID] = None):

        if not is_valid_string_with_rules(name):
            raise UnitError('Name is not correct')

        uuid = str(uuid)
        unit_uuid = self.db.exec(select(Unit.uuid).where(Unit.name == name)).first()
        unit_uuid = str(unit_uuid) if unit_uuid else unit_uuid

        if (uuid is None and unit_uuid) or (uuid and unit_uuid != uuid and unit_uuid is not None):
            raise UnitError('Name is not unique')
