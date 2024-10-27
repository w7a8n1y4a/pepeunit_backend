import uuid as uuid_pkg
from typing import Optional

from fastapi import Depends
from sqlalchemy import func, or_, text
from sqlalchemy.orm import aliased
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.utils import apply_enums, apply_ilike_search_string, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.unit_node import UnitNodeEdgeOutputFilter, UnitNodeOutputRead, UnitNodeRead
from app.services.validators import is_valid_uuid


class UnitNodeEdgeRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, unit_node_edge: UnitNodeEdge) -> UnitNodeEdge:
        self.db.add(unit_node_edge)
        self.db.commit()
        self.db.refresh(unit_node_edge)
        return unit_node_edge

    def get(self, unit_node_edge: UnitNodeEdge) -> Optional[UnitNodeEdge]:
        return self.db.get(UnitNodeEdge, unit_node_edge.uuid)

    def get_by_nodes(self, unit_nodes: list[UnitNode]) -> list[UnitNodeEdge]:

        uuids = [unit_node.uuid for unit_node in unit_nodes]

        return (
            self.db.query(UnitNodeEdge)
            .filter(
                or_(
                    UnitNodeEdge.node_input_uuid.in_(uuids),
                    UnitNodeEdge.node_output_uuid.in_(uuids),
                )
            )
            .all()
        )

    def get_all_count(self) -> int:
        return self.db.query(UnitNodeEdge.uuid).count()

    def check(self, unit_node_edge: UnitNodeEdge) -> bool:
        check = (
            self.db.query(UnitNodeEdge)
            .filter(
                UnitNodeEdge.node_input_uuid == unit_node_edge.node_input_uuid,
                UnitNodeEdge.node_output_uuid == unit_node_edge.node_output_uuid,
            )
            .first()
        )

        return bool(check)

    def delete(self, uuid: uuid_pkg.UUID) -> None:
        self.db.query(UnitNodeEdge).filter(UnitNodeEdge.uuid == uuid).delete()
        self.db.commit()

    def get_output_unit_nodes(
        self, filters: UnitNodeEdgeOutputFilter, restriction: list[str] = None
    ) -> list[tuple[Unit, list[dict]]]:

        unit_node_edge_alias = aliased(UnitNodeEdge)
        unit_node_alias = aliased(UnitNode)

        unit_node_subquery = (
            self.db.query(func.json_agg(text('units_nodes')).label('test'))
            .select_from(unit_node_alias)
            .join(unit_node_edge_alias, unit_node_edge_alias.node_output_uuid == unit_node_alias.uuid)
            .filter(
                unit_node_edge_alias.node_input_uuid == is_valid_uuid(filters.unit_node_input_uuid),
                unit_node_alias.unit_uuid == Unit.uuid,
            )
        )

        query = (
            self.db.query(Unit, unit_node_subquery.label('edges'))
            .select_from(Unit)
            .join(UnitNode, Unit.uuid == UnitNode.unit_uuid)
            .join(UnitNodeEdge, UnitNode.uuid == UnitNodeEdge.node_output_uuid)
            .filter(UnitNodeEdge.node_input_uuid == is_valid_uuid(filters.unit_node_input_uuid))
            .group_by(Unit.uuid)
        )

        if filters.creator_uuid:
            query = query.filter(UnitNode.creator_uuid == is_valid_uuid(filters.creator_uuid))

        if restriction:
            query = query.filter(UnitNode.uuid.in_(restriction))

        fields = [Unit.name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': UnitNode.visibility_level}
        query = apply_enums(query, filters, fields)

        fields = {'order_by_create_date': Unit.create_datetime, 'order_by_unit_name': Unit.name}
        query = apply_orders_by(query, filters, fields)

        query = apply_offset_and_limit(query, filters)

        test = query.all()

        return test
