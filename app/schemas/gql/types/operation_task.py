import uuid as uuid_pkg
from datetime import datetime

import strawberry

from app.dto.enum import (
    OperationTaskStatus,
)
from app.dto.enum import (
    OperationTaskType as OperationTaskTypeEnum,
)
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type(name="OperationTask")
class OperationTaskType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID
    create_datetime: datetime
    start_datetime: datetime | None
    finish_datetime: datetime | None
    status: OperationTaskStatus
    result: str | None
    task_type: OperationTaskTypeEnum


@strawberry.type()
class OperationTasksResultType(TypeInputMixin):
    count: int
    operation_tasks: list[OperationTaskType] = strawberry.field(
        default_factory=list
    )
