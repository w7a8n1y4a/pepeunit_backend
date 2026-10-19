import uuid as uuid_pkg

from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.domain.unit_group_unit_model import UnitGroupUnit
from app.repositories.base_repository import BaseRepository


class UnitGroupUnitRepository(BaseRepository):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(UnitGroupUnit, db)

    def get_link(
        self, unit_group_uuid: uuid_pkg.UUID, unit_uuid: uuid_pkg.UUID
    ) -> UnitGroupUnit | None:
        return (
            self.db.query(UnitGroupUnit)
            .filter(
                UnitGroupUnit.unit_group_uuid == unit_group_uuid,
                UnitGroupUnit.unit_uuid == unit_uuid,
            )
            .first()
        )
