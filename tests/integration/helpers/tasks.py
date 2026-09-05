from datetime import UTC, datetime, timedelta

from app.domain.operation_task_model import OperationTask
from app.dto.enum import OperationTaskType
from app.repositories.operation_task_repository import OperationTaskRepository


def age_tasks(
    database,
    task_type: OperationTaskType,
    age: timedelta = timedelta(days=1),
) -> None:
    """Сдвигает историю задач в прошлое, чтобы cooldown не мешал прогону"""
    repository = OperationTaskRepository(database)
    moment = datetime.now(UTC) - age

    for task in (
        database.query(OperationTask)
        .where(OperationTask.task_type == task_type.value)
        .all()
    ):
        task.create_datetime = moment
        task.start_datetime = moment
        repository.update(task.uuid, task)


def latest_task(
    database,
    task_type: OperationTaskType,
) -> OperationTask | None:
    return OperationTaskRepository(database).get_latest_by_type(task_type)


def drop_task(database, uuid) -> None:
    try:
        OperationTaskRepository(database).delete(OperationTask(uuid=uuid))
    except Exception:
        pass
