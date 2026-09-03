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
    service: OperationTaskService = Depends(get_operation_task_service),
):
    count, tasks = service.list(filters)
    return OperationTasksResult(
        count=count,
        operation_tasks=[OperationTaskRead(**task.dict()) for task in tasks],
    )


@router.get("/{task_uuid}", response_model=OperationTaskRead)
def get_operation_task(
    task_uuid: uuid_pkg.UUID,
    service: OperationTaskService = Depends(get_operation_task_service),
):
    return OperationTaskRead(**service.get(task_uuid).dict())
