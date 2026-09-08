import pytest

from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskType
from app.schemas.pydantic.operation_task import OperationTaskCreate
from tests.integration.helpers.services import operation_task_service
from tests.integration.helpers.tasks import drop_task


@pytest.fixture
def crud_task(admin_user_token, database) -> OperationTask:
    task = operation_task_service(database, admin_user_token).create(
        OperationTaskCreate(task_type=OperationTaskType.UPDATE_REGISTRY)
    )
    yield task
    drop_task(database, task.uuid)
