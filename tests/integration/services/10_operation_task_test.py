import logging
import uuid as uuid_pkg
from datetime import UTC, datetime, timedelta

import pytest

from app import settings
from app.configs.errors import (
    NoAccessError,
    OperationTaskError,
    ValidationError,
)
from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskStatus, OperationTaskType
from app.repositories.operation_task_repository import OperationTaskRepository
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


def test_create_operation_task_anonymous(database) -> None:
    service = operation_task_service(database, None)
    with pytest.raises(NoAccessError):
        service.create(OperationTaskCreate(task_type=TASK_TYPE))


def test_get_operation_task(crud_task, admin_user_token, database) -> None:
    service = operation_task_service(database, admin_user_token)
    assert service.get(crud_task.uuid).uuid == crud_task.uuid


def test_get_operation_task_not_exist(admin_user_token, database) -> None:
    service = operation_task_service(database, admin_user_token)
    with pytest.raises(ValidationError):
        service.get(uuid_pkg.uuid4())


def test_get_operation_task_not_creator(
    crud_task, regular_user_token, database
) -> None:
    service = operation_task_service(database, regular_user_token)
    with pytest.raises(NoAccessError):
        service.get(crud_task.uuid)


def test_get_operation_task_anonymous(crud_task, database) -> None:
    service = operation_task_service(database, None)
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
    """Фильтр creator_uuid всегда переписывается на текущего агента"""
    service = operation_task_service(database, regular_user_token)
    count, tasks = service.list(
        OperationTaskFilter(creator_uuid=crud_task.creator_uuid)
    )
    assert all(task.uuid != crud_task.uuid for task in tasks)


def test_list_operation_tasks_anonymous(database) -> None:
    service = operation_task_service(database, None)
    with pytest.raises(NoAccessError):
        service.list(OperationTaskFilter())


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


def test_schedule_operation_without_result(
    crud_task, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)
    service.schedule(crud_task, lambda _db: None)

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert finished.result is None


def test_schedule_failed_operation(
    crud_task, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)

    def operation(_db):
        msg = "operation is broken"
        raise OperationTaskError(msg)

    service.schedule(crud_task, operation)

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.ERROR.value
    assert "operation is broken" in finished.result


def test_schedule_result_truncated(
    crud_task, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)
    service.schedule(
        crud_task,
        lambda _db: "x" * (OperationTaskService.MAX_RESULT_LENGTH * 2),
    )

    finished = wait_task_finish(database, crud_task)
    assert finished.status == OperationTaskStatus.SUCCESS.value
    assert len(finished.result) == OperationTaskService.MAX_RESULT_LENGTH


def test_is_valid_cooldown(crud_task, admin_user_token, database) -> None:
    service = operation_task_service(database, admin_user_token)

    service.is_valid_cooldown(TASK_TYPE, timedelta(seconds=0))
    with pytest.raises(OperationTaskError):
        service.is_valid_cooldown(TASK_TYPE, timedelta(hours=1))


def test_is_valid_cooldown_after_expiration(
    crud_task, admin_user_token, database
) -> None:
    service = operation_task_service(database, admin_user_token)
    age_tasks(database, TASK_TYPE)

    service.is_valid_cooldown(TASK_TYPE, timedelta(hours=1))


def test_get_latest_by_type(crud_task, admin_user, database) -> None:
    repository = OperationTaskRepository(database)
    assert (
        repository.get_latest_by_type(TASK_TYPE).uuid == crud_task.uuid
    )

    older = repository.create(
        OperationTask(
            creator_uuid=admin_user.uuid,
            task_type=TASK_TYPE.value,
            create_datetime=datetime.now(UTC) - timedelta(days=1),
            start_datetime=datetime.now(UTC) - timedelta(days=1),
        )
    )
    try:
        assert repository.get_latest_by_type(TASK_TYPE).uuid == crud_task.uuid
    finally:
        repository.delete(OperationTask(uuid=older.uuid))


def test_get_finish_text(crud_task) -> None:
    crud_task.result = None
    assert OperationTaskService._get_finish_text(crud_task) == (
        f"Task `{crud_task.task_type}` finish with `{crud_task.status}`"
    )

    crud_task.result = "Synced `2` of `3` registries"
    text = OperationTaskService._get_finish_text(crud_task)
    assert "Synced '2' of '3' registries" in text
    assert text.count("`") == 6


async def test_notify_telegram_disabled(crud_task, database) -> None:
    await OperationTaskService._notify_telegram(crud_task, database, False)


async def test_notify_telegram_without_chat_id(
    extra_user, extra_user_token, database
) -> None:
    service = operation_task_service(database, extra_user_token)
    task = service.create(OperationTaskCreate(task_type=TASK_TYPE))

    await OperationTaskService._notify_telegram(task, database, True)
    assert not extra_user.telegram_chat_id
