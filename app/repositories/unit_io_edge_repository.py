import uuid as uuid_pkg

from fastapi import Depends
from sqlalchemy import and_, or_
from sqlalchemy.orm import aliased
from sqlmodel import Session, func, select

from app.configs.db import get_session
from app.domain.unit_io_edge_model import UnitIOEdge
from app.domain.unit_io_model import UnitIO
from app.dto.enum import UuidEntity, VisibilityLevel
from app.repositories.base_repository import BaseRepository
from app.services.validators import is_valid_uuid


class UnitIOEdgeRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(UnitIOEdge, db)

    def get_by_nodes(self, unit_ios: list[UnitIO]) -> list[UnitIOEdge]:
        uuids = [unit_io.uuid for unit_io in unit_ios]

        return (
            self.db.query(UnitIOEdge)
            .filter(
                or_(
                    UnitIOEdge.input_uuid.in_(uuids),
                    UnitIOEdge.output_uuid.in_(uuids),
                )
            )
            .all()
        )

    def get_by_two_uuid(
        self, input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID
    ):
        return (
            self.db.query(UnitIOEdge)
            .filter(
                UnitIOEdge.input_uuid
                == is_valid_uuid(input_uuid, UuidEntity.UNIT_IO_INPUT),
                UnitIOEdge.output_uuid
                == is_valid_uuid(output_uuid, UuidEntity.UNIT_IO_OUTPUT),
            )
            .first()
        )

    def check(self, unit_io_edge: UnitIOEdge) -> bool:
        check = (
            self.db.query(UnitIOEdge)
            .filter(
                UnitIOEdge.input_uuid == unit_io_edge.input_uuid,
                UnitIOEdge.output_uuid == unit_io_edge.output_uuid,
            )
            .first()
        )

        return bool(check)

    def count_by_input_node(self, input_uuid: uuid_pkg.UUID) -> int:
        """Count the number of edges connected to an input node"""
        return (
            self.db.query(UnitIOEdge)
            .filter(
                UnitIOEdge.input_uuid
                == is_valid_uuid(input_uuid, UuidEntity.UNIT_IO_INPUT)
            )
            .count()
        )

    def count_by_output_node(self, output_uuid: uuid_pkg.UUID) -> int:
        """Count the number of edges connected from an output node"""
        return (
            self.db.query(UnitIOEdge)
            .filter(
                UnitIOEdge.output_uuid
                == is_valid_uuid(output_uuid, UuidEntity.UNIT_IO_OUTPUT)
            )
            .count()
        )

    def get_public_count(self) -> int:
        input_node = aliased(UnitIO)
        output_node = aliased(UnitIO)
        return self.db.exec(
            select(func.count())
            .select_from(UnitIOEdge)
            .join(
                input_node,
                UnitIOEdge.input_uuid == input_node.uuid,
            )
            .join(
                output_node,
                UnitIOEdge.output_uuid == output_node.uuid,
            )
            .where(
                and_(
                    input_node.visibility_level
                    == VisibilityLevel.PUBLIC.value,
                    output_node.visibility_level
                    == VisibilityLevel.PUBLIC.value,
                )
            )
        ).one()
