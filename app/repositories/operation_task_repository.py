import uuid as uuid_pkg

from fastapi import Depends
from sqlmodel import Session, col

from app.configs.db import get_session
from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskType
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.gql.inputs.operation_task import OperationTaskFilterInput
from app.schemas.pydantic.operation_task import OperationTaskFilter


class OperationTaskRepository(BaseRepository[OperationTask]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(OperationTask, db)

    def get_for_user(
        self,
        task_uuid: uuid_pkg.UUID,
        creator_uuid: uuid_pkg.UUID,
    ) -> OperationTask | None:
        return (
            self.db.query(OperationTask)
            .filter(
                OperationTask.uuid == task_uuid,
                OperationTask.creator_uuid == creator_uuid,
            )
            .first()
        )

    def list_for_user(
        self,
        creator_uuid: uuid_pkg.UUID,
        filters: OperationTaskFilter | OperationTaskFilterInput,
    ) -> tuple[int, list[OperationTask]]:
        query = self.db.query(OperationTask).filter(
            OperationTask.creator_uuid == creator_uuid
        )

        fields = {
            "status": OperationTask.status,
            "task_type": OperationTask.task_type,
        }
        query = apply_enums(query, filters, fields)

        query = query.order_by(
            col(OperationTask.start_datetime).desc().nullslast(),
            col(OperationTask.create_datetime).desc(),
        )
        count, query = apply_offset_and_limit(query, filters)
        return count, query.all()

    def get_latest_by_type(
        self,
        task_type: OperationTaskType,
    ) -> OperationTask | None:
        return (
            self.db.query(OperationTask)
            .filter(OperationTask.task_type == task_type.value)
            .order_by(OperationTask.create_datetime.desc())
            .first()
        )
