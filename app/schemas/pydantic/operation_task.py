import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import (
    OperationTaskStatus,
    OperationTaskType,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class OperationTaskCreate(BaseModel):
    task_type: OperationTaskType


class OperationTaskRead(BaseModel):
    uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID
    create_datetime: datetime
    start_datetime: datetime | None
    finish_datetime: datetime | None
    status: OperationTaskStatus
    result: str | None
    task_type: OperationTaskType


@dataclass
class OperationTaskFilter(BasePaginationRestMixin):
    creator_uuid: uuid_pkg.UUID | None = None

    status: list[str] | None = Query(
        [item.value for item in OperationTaskStatus]
    )
    task_type: list[str] | None = Query(
        [item.value for item in OperationTaskType]
    )

    def dict(self):
        return self.__dict__


class OperationTasksResult(BaseModel):
    count: int
    operation_tasks: list[OperationTaskRead]
