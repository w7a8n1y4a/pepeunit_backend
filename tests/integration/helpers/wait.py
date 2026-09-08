import time
from collections.abc import Callable

import pytest

from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskStatus
from app.repositories.operation_task_repository import OperationTaskRepository


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 20,
    interval: float = 1,
    message: str = "condition not met",
    session=None,
) -> None:
    deadline = time.monotonic() + timeout
    while True:
        if session is not None:
            session.expire_all()
        if predicate():
            return
        if time.monotonic() >= deadline:
            pytest.fail(f"{message} (waited {timeout}s)")
        time.sleep(interval)


def wait_task_finish(
    database,
    task,
    *,
    timeout: float = 120,
) -> OperationTask:
    repository = OperationTaskRepository(database)

    def is_finish() -> bool:
        finished = repository.get(OperationTask(uuid=task.uuid))
        return (
            finished is not None
            and finished.status != OperationTaskStatus.RUNNING.value
        )

    wait_until(
        is_finish,
        timeout=timeout,
        message=f"OperationTask {task.task_type} not finished",
        session=database,
    )
    return repository.get(OperationTask(uuid=task.uuid))
