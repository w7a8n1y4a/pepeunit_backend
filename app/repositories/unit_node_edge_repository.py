import uuid as uuid_pkg

from fastapi import Depends
from sqlalchemy import or_
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.base_repository import BaseRepository
from app.services.validators import is_valid_uuid


class UnitNodeEdgeRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(UnitNodeEdge, db)

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

    def get_by_two_uuid(self, input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID):
        return (
            self.db.query(UnitNodeEdge)
            .filter(
                UnitNodeEdge.node_input_uuid == is_valid_uuid(input_uuid),
                UnitNodeEdge.node_output_uuid == is_valid_uuid(output_uuid),
            )
            .first()
        )

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
