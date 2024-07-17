from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_node_edge_model import UnitNodeEdge


class UnitNodeEdgeRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, unit_node_edge: UnitNodeEdge) -> UnitNodeEdge:
        self.db.add(unit_node_edge)
        self.db.commit()
        self.db.refresh(unit_node_edge)
        return unit_node_edge

    def get(self, unit_node_edge: UnitNodeEdge) -> UnitNodeEdge:
        return self.db.get(UnitNodeEdge, unit_node_edge.uuid)

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

    def delete(self, uuid: str) -> None:
        self.db.query(UnitNodeEdge).filter(UnitNodeEdge.uuid == uuid).delete()
        self.db.commit()
