from fastapi import Depends
from sqlmodel import Session, col

from app.configs.db import get_session
from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskType
from app.repositories.base_repository import BaseRepository
from app.repositories.utils import apply_enums, apply_offset_and_limit
from app.schemas.gql.inputs.operation_task import OperationTaskFilterInput
from app.schemas.pydantic.operation_task import OperationTaskFilter
from app.services.validators import is_valid_uuid


class OperationTaskRepository(BaseRepository[OperationTask]):
    def __init__(self, db: Session = Depends(get_session)) -> None:
        super().__init__(OperationTask, db)

    def list(
        self, filters: OperationTaskFilter | OperationTaskFilterInput
    ) -> tuple[int, list[OperationTask]]:
        query = self.db.query(OperationTask)

        if filters.creator_uuid:
            query = query.filter(
                OperationTask.creator_uuid
                == is_valid_uuid(filters.creator_uuid)
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
        self, task_type: OperationTaskType
    ) -> OperationTask | None:
        count, tasks = self.list(
            OperationTaskFilter(task_type=[task_type.value], limit=1)
        )
        return tasks[0] if tasks else None
