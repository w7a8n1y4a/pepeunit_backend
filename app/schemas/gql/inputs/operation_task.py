import uuid as uuid_pkg

import strawberry

from app.dto.enum import OperationTaskStatus, OperationTaskType
from app.schemas.gql.type_input_mixin import BasePaginationGql


@strawberry.input()
class OperationTaskFilterInput(BasePaginationGql):
    creator_uuid: uuid_pkg.UUID | None = None

    status: list[OperationTaskStatus] | None = tuple(OperationTaskStatus)
    task_type: list[OperationTaskType] | None = tuple(OperationTaskType)
