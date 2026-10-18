import signal
import time

import pytest

from app.configs.errors import NoAccessError, UserError
from app.domain.operation_task_model import OperationTask
from app.domain.user_model import User
from app.dto.enum import OperationTaskStatus, OperationTaskType, UserRole
from app.repositories.operation_task_repository import OperationTaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.instance_settings import InstanceSettingsUpdate
from app.schemas.pydantic.user import UserCreate
from app.services.instance_settings_service import InstanceSettingsService
from tests.integration.helpers.instance_settings import wait_runtime
from tests.integration.helpers.keys import fresh_key
from tests.integration.helpers.services import (
    instance_settings_service,
    user_service,
)


def _as_owner(database, user: User):
    repository = UserRepository(db=database)
    previous = repository.get_owner()
    repository.set_single_owner(user.uuid)
    return repository, previous


def _restore_owner(database, repository, user: User, previous: User | None):
    database.expire_all()
    user.role = UserRole.USER
    repository.update(user.uuid, user)
    if previous and previous.uuid != user.uuid:
        repository.set_single_owner(previous.uuid)


def test_settings_are_owner_only(
    database, extra_user, extra_user_token, admin_user_token
) -> None:
    with pytest.raises(NoAccessError):
        instance_settings_service(database, extra_user_token).get()
    with pytest.raises(NoAccessError):
        instance_settings_service(database, admin_user_token).update(
            InstanceSettingsUpdate(pu_instance_user_max_group=8)
        )

    repository, previous = _as_owner(database, extra_user)
    try:
        instance_settings_service(database, extra_user_token).get()
    finally:
        _restore_owner(database, repository, extra_user, previous)


def test_user_count_limit(database, cc, extra_user, extra_user_token) -> None:
    repository, previous = _as_owner(database, extra_user)
    settings_service = instance_settings_service(database, extra_user_token)
    current = settings_service.get().pu_instance_user_max_count
    limit = UserRepository(database).get_all_count()
    try:
        settings_service.update(
            InstanceSettingsUpdate(pu_instance_user_max_count=limit)
        )
        wait_runtime("pu_instance_user_max_count", limit)
        with pytest.raises(UserError):
            user_service(database, cc, None).create(
                UserCreate(public_key=fresh_key().public_key)
            )
    finally:
        settings_service.update(
            InstanceSettingsUpdate(pu_instance_user_max_count=current)
        )
        wait_runtime("pu_instance_user_max_count", current)
        _restore_owner(database, repository, extra_user, previous)


def test_rescue_kills_workers_when_master_stays(monkeypatch, tmp_path) -> None:
    from app.configs.restart import ServerRestart

    flag = tmp_path / "instance_restart"
    flag.write_text("1")
    killed: list[tuple[int, int]] = []
    clock = {"now": 0.0}
    restarter = ServerRestart()
    restarter.flag = flag
    monkeypatch.setattr(time, "monotonic", lambda: clock["now"])

    def _sleep(_seconds: float) -> None:
        clock["now"] += 1

    monkeypatch.setattr(time, "sleep", _sleep)
    monkeypatch.setattr(ServerRestart, "_alive", lambda _self, _pid: True)
    monkeypatch.setattr(ServerRestart, "_child_pids", lambda _self, _pid: [2, 3])
    monkeypatch.setattr(ServerRestart, "_cwd", lambda _self, _pid: "")

    def _kill(_self, pid: int, sig: int) -> None:
        killed.append((pid, sig))
        flag.unlink(missing_ok=True)

    monkeypatch.setattr(ServerRestart, "_kill", _kill)

    restarter.rescue(10)

    assert killed == [(2, signal.SIGKILL), (3, signal.SIGKILL)]


def test_reboot_stops_the_master(monkeypatch) -> None:
    requested: list[str] = []
    monkeypatch.setattr(
        "app.services.instance_settings_service.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setattr(
        "app.services.instance_settings_service.restart.request",
        lambda: requested.append("restart"),
    )

    InstanceSettingsService._restart_after_response()

    assert requested == ["restart"]


def test_reboot_is_marked_on_start(
    database, extra_user, extra_user_token, monkeypatch
) -> None:
    repository, previous = _as_owner(database, extra_user)
    monkeypatch.setattr(
        InstanceSettingsService, "_restart_after_response", lambda: None
    )
    try:
        task = instance_settings_service(database, extra_user_token).reboot()
        assert task.task_type == OperationTaskType.REBOOT_INSTANCE.value
        assert task.status == OperationTaskStatus.RUNNING.value

        InstanceSettingsService.mark_started(database)
        database.expire_all()
        finished = OperationTaskRepository(database).get(
            OperationTask(uuid=task.uuid)
        )
        assert finished.status == OperationTaskStatus.SUCCESS.value
        assert finished.result == "Instance started"
        assert finished.finish_datetime is not None
    finally:
        _restore_owner(database, repository, extra_user, previous)
