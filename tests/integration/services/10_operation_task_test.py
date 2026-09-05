import logging
from datetime import timedelta

import pytest

from app import settings
from app.configs.errors import NoAccessError, OperationTaskError
from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskStatus, OperationTaskType
from app.dto.integration_tests import IntegrationTestsStats
from app.schemas.pydantic.operation_task import (
    OperationTaskCreate,
    OperationTaskFilter,
)
from app.services.operation_task_service import OperationTaskService
from tests.integration.helpers.services import operation_task_service
from tests.integration.helpers.tasks import age_tasks, drop_task
from tests.integration.helpers.wait import wait_task_finish

TASK_TYPE = OperationTaskType.UPDATE_REGISTRY


@pytest.fixture
def crud_task(admin_user_token, database) -> OperationTask:
    service = operation_task_service(database, admin_user_token)
    task = service.create(OperationTaskCreate(task_type=TASK_TYPE))
    yield task
    drop_task(database, task.uuid)


def test_create_operation_task(crud_task, admin_user) -> None:
    logging.info(crud_task.uuid)
    assert crud_task.task_type == TASK_TYPE.value
    assert crud_task.status == OperationTaskStatus.RUNNING.value
    assert crud_task.creator_uuid == admin_user.uuid
    assert crud_task.create_datetime == crud_task.start_datetime
    assert crud_task.finish_datetime is None
    assert crud_task.result is None


def test_operation_task_anonymous(crud_task, database) -> None:
    service = operation_task_service(database, None)
    for operation in (
        lambda: service.create(OperationTaskCreate(task_type=TASK_TYPE)),
        lambda: service.get(crud_task.uuid),
        lambda: service.list(OperationTaskFilter()),
    ):
        with pytest.raises(NoAccessError):
            operation()


def test_get_operation_task(crud_task, admin_user_token, database) -> None:
    service = operation_task_service(database, admin_user_token)
    assert service.get(crud_task.uuid).uuid == crud_task.uuid


def test_get_operation_task_not_creator(
    crud_task, regular_user_token, database
) -> None:
    service = operation_task_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.get(crud_task.uuid)


def test_list_operation_tasks(
    crud_task, admin_user, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)

    count, tasks = service.list(OperationTaskFilter())
    assert count >= 1
    assert any(task.uuid == crud_task.uuid for task in tasks)
    assert all(task.creator_uuid == admin_user.uuid for task in tasks)

    count, tasks = service.list(
        OperationTaskFilter(
            task_type=[TASK_TYPE.value],
            status=[OperationTaskStatus.RUNNING.value],
            offset=0,
            limit=settings.pu_max_pagination_size,
        )
    )
    assert all(task.task_type == TASK_TYPE.value for task in tasks)
    assert all(
        task.status == OperationTaskStatus.RUNNING.value for task in tasks
    )
    assert any(task.uuid == crud_task.uuid for task in tasks)

    count, tasks = service.list(
        OperationTaskFilter(
            task_type=[OperationTaskType.SCAN_INSTANCE.value],
            status=[OperationTaskStatus.SUCCESS.value],
        )
    )
    assert all(task.uuid != crud_task.uuid for task in tasks)


def test_list_operation_tasks_only_own(
    crud_task, regular_user_token, database
) -> None:
    """The creator_uuid filter is always rewritten to the current agent"""
    service = operation_task_service(database, regular_user_token)
    count, tasks = service.list(
        OperationTaskFilter(creator_uuid=crud_task.creator_uuid)
    )
    assert all(task.uuid != crud_task.uuid for task in tasks)


def test_schedule_sync_operation(
    crud_task, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)
    service.schedule(crud_task, lambda _db: "sync done")

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result == "sync done"
    assert finished.finish_datetime


def test_schedule_async_operation(
    crud_task, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)

    async def operation(_db) -> str:
        return "async done"

    service.schedule(crud_task, operation)

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result == "async done"


def test_schedule_failed_operation(
    crud_task, admin_user_token, database
) -> None:
    """A result keeps a raw error, without the http prefix of it"""
    service = operation_task_service(database, admin_user_token)

    def operation(_db):
        msg = "operation is broken"
        raise OperationTaskError(msg)

    service.schedule(crud_task, operation)

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.ERROR.value
    assert finished.result == "operation is broken"


def test_schedule_log_result(crud_task, admin_user_token, database) -> None:
    """A full test log is stored without any truncation"""
    log = "1 failed, 12 passed\n" + "x" * 65536 + "\nlast log line"

    service = operation_task_service(database, admin_user_token)
    service.schedule(crud_task, lambda _db: log)

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result == log


def test_is_valid_cooldown(crud_task, admin_user_token, database) -> None:
    service = operation_task_service(database, admin_user_token)

    service.is_valid_cooldown(TASK_TYPE, timedelta(seconds=0))
    with pytest.raises(OperationTaskError):
        service.is_valid_cooldown(TASK_TYPE, timedelta(hours=1))

    age_tasks(database, TASK_TYPE)
    service.is_valid_cooldown(TASK_TYPE, timedelta(hours=1))


def test_get_finish_text(crud_task) -> None:
    """A test log is replaced with its counts, other results keep the tail"""
    crud_task.result = None
    assert OperationTaskService._get_finish_text(crud_task) == (
        f"Task `{crud_task.task_type}` finish with `{crud_task.status}`"
    )

    crud_task.result = "Synced `2` of `3` registries"
    text = OperationTaskService._get_finish_text(crud_task)
    assert "Synced '2' of '3' registries" in text
    assert text.count("`") == 6

    crud_task.result = "y" * 65536 + "last log line"
    text = OperationTaskService._get_finish_text(crud_task)
    assert "last log line`" in text
    assert len(text.split("`")[-2]) == (
        IntegrationTestsStats.MAX_TELEGRAM_RESULT_LENGTH
    )

    crud_task.task_type = OperationTaskType.INTEGRATION_TESTS.value
    crud_task.status = OperationTaskStatus.SUCCESS.value
    crud_task.result = (
        "collected 241 items\n"
        + "y" * 65536
        + "\n==== 231 passed, 10 skipped in 174.21s (0:02:54) ====\n"
    )
    assert OperationTaskService._get_finish_text(crud_task) == (
        "Task `IntegrationTests` finish with `Success`: `total 241,"
        " passed 231, skipped 10, failed 0, error 0 in 174.21s`"
    )
