from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_node_model import UnitNode
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by


class UnitNodeFilter:
    pass


class UnitNodeRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def create(self, unit_node: UnitNode) -> UnitNode:
        self.db.add(unit_node)
        self.db.commit()
        self.db.refresh(unit_node)
        return unit_node

    def get(self, unit_node: UnitNode) -> UnitNode:
        return self.db.get(UnitNode, unit_node.uuid)

    def update(self, uuid, unit_node: UnitNode) -> UnitNode:
        unit_node.uuid = uuid
        self.db.merge(unit_node)
        self.db.commit()
        return self.get(unit_node)

    def delete(self, unit_node: UnitNode) -> None:
        self.db.delete(self.get(unit_node))
        self.db.commit()
        self.db.flush()

    def list(self, filters: UnitNodeFilter) -> list[UnitNode]:
        query = self.db.query(UnitNode)

        fields = [UnitNode.topic_name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': UnitNode.visibility_level, 'type': UnitNode.type}
        query = apply_enums(query, filters, fields)

        fields = {'order_by_create_date': UnitNode.create_datetime}
        query = apply_orders_by(query, filters, fields)

        query = apply_offset_and_limit(query, filters)
        return query.all()
