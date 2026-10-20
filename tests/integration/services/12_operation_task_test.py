import logging

import pytest

from app.configs.errors import NoAccessError
from app.domain.notification_model import Notification
from app.dto.enum import OperationTaskStatus, OperationTaskType
from app.repositories.operation_task_repository import OperationTaskRepository
from app.schemas.pydantic.operation_task import OperationTaskCreate
from app.services.operation_task_service import OperationTaskService
from tests.integration.helpers.notifications import process_saved
from tests.integration.helpers.services import (
    notification_service,
    operation_task_service,
)

TASK_TYPE = OperationTaskType.UPDATE_REGISTRY


def _task_alerts(database, user_uuid) -> list[Notification]:
    return (
        database.query(Notification)
        .filter(
            Notification.user_uuid == user_uuid,
            Notification.type == TASK_TYPE.value,
        )
        .all()
    )


def test_create_operation_task(crud_task, admin_user) -> None:
    logging.info(crud_task.uuid)
    assert crud_task.task_type == TASK_TYPE.value
    assert crud_task.status == OperationTaskStatus.RUNNING.value
    assert crud_task.creator_uuid == admin_user.uuid
    assert crud_task.finish_datetime is None


@pytest.mark.notification
def test_operation_task_start_alert(crud_task, admin_user, database) -> None:
    started = [
        row
        for row in _task_alerts(database, admin_user.uuid)
        if row.data["status"] == OperationTaskStatus.RUNNING.value
    ]
    assert started
    assert started[-1].is_processed is False
    assert started[-1].is_read is False
    assert started[-1].user_uuid == crud_task.creator_uuid


@pytest.mark.notification
def test_operation_task_finish_alert(
    crud_task, admin_user, admin_user_token, database, cc
) -> None:
    finished = OperationTaskService._finish(
        OperationTaskRepository(database),
        crud_task.uuid,
        OperationTaskStatus.SUCCESS,
        "1 passed",
    )
    OperationTaskService._record_alert(database, finished)

    pending = [
        row
        for row in _task_alerts(database, admin_user.uuid)
        if not row.is_processed
    ]
    assert len(pending) >= 2
    process_saved(
        notification_service(database, cc, admin_user_token), pending
    )

    stored = [
        row
        for row in _task_alerts(database, admin_user.uuid)
        if row.table_text is not None
    ]
    assert all(row.big_text is None for row in stored)
    assert any(row.small_text == "UpdateRegistry: Running" for row in stored)
    assert any(row.small_text == "UpdateRegistry: 1 passed" for row in stored)
    texts = [row.table_text for row in stored]
    assert any(
        "Update Registry" in text and "Running" in text for text in texts
    )
    assert any(
        "Update Registry" in text and "Success" in text and "1 passed" in text
        for text in texts
    )


def test_operation_task_anonymous(database) -> None:
    service = operation_task_service(database, None)
    with pytest.raises(NoAccessError):
        service.create(OperationTaskCreate(task_type=TASK_TYPE))
