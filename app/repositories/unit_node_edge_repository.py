import uuid as uuid_pkg
from typing import Optional

from fastapi import Depends
from sqlalchemy import or_
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.pydantic.unit_node import UnitNodeEdgeOutputFilter
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

    def get_output_unit_nodes(self, filters: UnitNodeEdgeOutputFilter, restriction: list[str] = None) -> list[UnitNode]:
        query = self.db.query(UnitNode).join(UnitNodeEdge, UnitNode.uuid == UnitNodeEdge.node_output_uuid)

        query = query.filter(UnitNodeEdge.node_input_uuid == is_valid_uuid(filters.unit_node_input_uuid))

        if restriction:
            query = query.filter(UnitNode.uuid.in_(restriction))


        fields = {'visibility_level': UnitNode.visibility_level}
        query = apply_enums(query, filters, fields)

        query = apply_offset_and_limit(query, filters)
        return query.all()