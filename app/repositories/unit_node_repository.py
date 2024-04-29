from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import UnitNodeType
from app.repositories.utils import apply_ilike_search_string, apply_enums, apply_offset_and_limit, apply_orders_by
from app.schemas.pydantic.unit_node import UnitNodeFilter


class UnitNodeRepository:
    db: Session

    def __init__(self, db: Session = Depends(get_session)) -> None:
        self.db = db

    def bulk_save(self, unit_nodes: list[UnitNode]) -> None:
        self.db.bulk_save_objects(unit_nodes)
        self.db.commit()

    def get(self, unit_node: UnitNode) -> UnitNode:
        return self.db.get(UnitNode, unit_node.uuid)

    def get_output_topic(self, unit_uuid, unit_node: UnitNode) -> UnitNode:
        return (
            self.db.query(UnitNode)
            .filter(
                UnitNode.unit_uuid == unit_uuid,
                UnitNode.topic_name == unit_node.topic_name,
                UnitNode.type == UnitNodeType.OUTPUT,
            )
            .first()
        )

    def get_unit_nodes(self, unit: Unit) -> list[UnitNode]:
        query = self.db.query(UnitNode).filter(UnitNode.unit_uuid == unit.uuid)
        return query.all()

    def update(self, uuid, unit_node: UnitNode) -> UnitNode:
        unit_node.uuid = uuid
        self.db.merge(unit_node)
        self.db.commit()
        return self.get(unit_node)

    def delete(self, del_uuid_list: list[str]) -> None:
        self.db.query(UnitNode).filter(UnitNode.uuid.in_(del_uuid_list)).delete()
        self.db.commit()

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
