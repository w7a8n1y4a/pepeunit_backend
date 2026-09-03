import uuid as uuid_pkg

import strawberry
from strawberry.types import Info

from app.configs.gql import get_operation_task_service_gql
from app.schemas.gql.inputs.operation_task import OperationTaskFilterInput
from app.schemas.gql.types.operation_task import (
    OperationTasksResultType,
    OperationTaskType,
)


@strawberry.field()
def get_operation_task(
    info: Info,
    uuid: uuid_pkg.UUID,
) -> OperationTaskType:
    task = get_operation_task_service_gql(info).get(uuid)
    return OperationTaskType(**task.dict())


@strawberry.field()
def get_operation_tasks(
    filters: OperationTaskFilterInput, info: Info
) -> OperationTasksResultType:
    count, tasks = get_operation_task_service_gql(info).list(filters)
    return OperationTasksResultType(
        count=count,
        operation_tasks=[OperationTaskType(**task.dict()) for task in tasks],
    )
