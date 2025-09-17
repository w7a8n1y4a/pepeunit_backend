import uuid as uuid_pkg

from fastapi import Depends
from fastapi.params import Query
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import (
    apply_enums,
    apply_ilike_search_string,
    apply_offset_and_limit,
    apply_orders_by,
    apply_restriction,
)
from app.schemas.pydantic.unit_node import UnitNodeFilter
from app.services.validators import is_valid_uuid


class UnitNodeRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(UnitNode, db)

    def bulk_save(self, unit_nodes: list[UnitNode]) -> None:
        self.db.bulk_save_objects(unit_nodes)
        self.db.commit()

    def get_by_topic(self, unit_uuid: uuid_pkg.UUID, unit_node: UnitNode) -> UnitNode:
        return (
            self.db.query(UnitNode)
            .filter(
                UnitNode.unit_uuid == unit_uuid,
                UnitNode.topic_name == unit_node.topic_name,
                UnitNode.type == unit_node.type,
            )
            .first()
        )

    def get_nodes_with_edges(self, unit_uuid: uuid_pkg.UUID) -> list[tuple]:

        unit_node_edge_alias = aliased(UnitNodeEdge)
        unit_node_alias = aliased(UnitNode)

        edge_subquery = (
            self.db.query(
                func.json_agg(
                    func.json_build_array(unit_node_edge_alias.node_output_uuid, unit_node_alias.topic_name)
                ).label('test')
            )
            .select_from(unit_node_edge_alias)
            .join(unit_node_alias, unit_node_edge_alias.node_output_uuid == unit_node_alias.uuid)
            .filter(unit_node_edge_alias.node_input_uuid == UnitNode.uuid)
        )

        return (
            self.db.query(UnitNode.uuid, UnitNode.topic_name, UnitNode.type, edge_subquery.label('edges'))
            .select_from(UnitNodeEdge)
            .outerjoin(UnitNode, UnitNodeEdge.node_input_uuid == UnitNode.uuid, full=True)
            .filter(UnitNode.unit_uuid == unit_uuid)
            .group_by(UnitNode.uuid, UnitNode.topic_name, UnitNode.type)
            .all()
        )

    def delete(self, del_uuid_list: list[str]) -> None:
        self.db.query(UnitNode).filter(UnitNode.uuid.in_(del_uuid_list)).delete()
        self.db.commit()

    def list(self, filters: UnitNodeFilter, restriction: list[str] = None) -> tuple[int, list[UnitNode]]:
        query = self.db.query(UnitNode)

        if filters.output_uuid:
            query = query.join(UnitNodeEdge, UnitNodeEdge.node_input_uuid == UnitNode.uuid).filter(
                UnitNodeEdge.node_output_uuid == filters.output_uuid
            )

        filters.uuids = filters.uuids.default if isinstance(filters.uuids, Query) else filters.uuids
        if filters.uuids:
            query = query.filter(UnitNode.uuid.in_([is_valid_uuid(item) for item in filters.uuids]))

        if filters.unit_uuid:
            query = query.filter(UnitNode.unit_uuid == is_valid_uuid(filters.unit_uuid))

        fields = [UnitNode.topic_name]
        query = apply_ilike_search_string(query, filters, fields)

        fields = {'visibility_level': UnitNode.visibility_level, 'type': UnitNode.type}
        query = apply_enums(query, filters, fields)

        query = apply_restriction(query, filters, UnitNode, restriction)

        fields = {'order_by_create_date': UnitNode.create_datetime}
        query = apply_orders_by(query, filters, fields)

        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()
