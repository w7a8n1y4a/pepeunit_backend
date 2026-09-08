import uuid as uuid_pkg

from fastapi import APIRouter, Depends

from app.configs.rest import get_operation_task_service
from app.schemas.pydantic.operation_task import (
    OperationTaskFilter,
    OperationTaskRead,
    OperationTasksResult,
)
from app.services.operation_task_service import OperationTaskService

router = APIRouter()


@router.get("", response_model=OperationTasksResult)
def get_operation_tasks(
    filters: OperationTaskFilter = Depends(OperationTaskFilter),
    operation_task_service: OperationTaskService = Depends(
        get_operation_task_service
    ),
):
    count, tasks = operation_task_service.list(filters)
    return OperationTasksResult(
        count=count,
        operation_tasks=[OperationTaskRead(**task.dict()) for task in tasks],
    )


@router.get("/{uuid}", response_model=OperationTaskRead)
def get_operation_task(
    uuid: uuid_pkg.UUID,
    operation_task_service: OperationTaskService = Depends(
        get_operation_task_service
    ),
):
    return OperationTaskRead(**operation_task_service.get(uuid).dict())
