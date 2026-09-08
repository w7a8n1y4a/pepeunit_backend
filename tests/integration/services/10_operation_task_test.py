import logging

import pytest

from app.configs.errors import NoAccessError
from app.dto.enum import OperationTaskStatus, OperationTaskType
from app.schemas.pydantic.operation_task import (
    OperationTaskCreate,
    OperationTaskFilter,
)
from tests.integration.helpers.services import operation_task_service

TASK_TYPE = OperationTaskType.UPDATE_REGISTRY


def test_create_operation_task(crud_task, admin_user) -> None:
    logging.info(crud_task.uuid)
    assert crud_task.task_type == TASK_TYPE.value
    assert crud_task.status == OperationTaskStatus.RUNNING.value
    assert crud_task.creator_uuid == admin_user.uuid
    assert crud_task.finish_datetime is None


def test_get_operation_task(crud_task, admin_user_token, database) -> None:
    service = operation_task_service(database, admin_user_token)
    assert service.get(crud_task.uuid).uuid == crud_task.uuid


def test_get_operation_task_not_creator(
    crud_task, regular_user_token, database
) -> None:
    service = operation_task_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.get(crud_task.uuid)


def test_get_many_operation_task(
    crud_task, admin_user, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)

    count, tasks = service.list(OperationTaskFilter.unlimited())
    assert count >= 1
    assert any(task.uuid == crud_task.uuid for task in tasks)
    assert all(task.creator_uuid == admin_user.uuid for task in tasks)

    count, tasks = service.list(
        OperationTaskFilter.unlimited(
            task_type=[TASK_TYPE.value],
            status=[OperationTaskStatus.RUNNING.value],
        )
    )
    assert all(task.task_type == TASK_TYPE.value for task in tasks)
    assert any(task.uuid == crud_task.uuid for task in tasks)


def test_list_operation_tasks_only_own(
    crud_task, regular_user_token, database
) -> None:
    service = operation_task_service(database, regular_user_token)
    count, tasks = service.list(
        OperationTaskFilter.unlimited(creator_uuid=crud_task.creator_uuid)
    )
    assert all(task.uuid != crud_task.uuid for task in tasks)


def test_operation_task_anonymous(crud_task, database) -> None:
    service = operation_task_service(database, None)
    with pytest.raises(NoAccessError):
        service.create(OperationTaskCreate(task_type=TASK_TYPE))
    with pytest.raises(NoAccessError):
        service.get(crud_task.uuid)
    with pytest.raises(NoAccessError):
        service.list(OperationTaskFilter())
