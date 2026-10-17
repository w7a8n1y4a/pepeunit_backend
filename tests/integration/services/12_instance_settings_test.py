import pytest

from app.configs.errors import NoAccessError, UserError
from app.domain.operation_task_model import OperationTask
from app.domain.user_model import User
from app.dto.enum import OperationTaskStatus, OperationTaskType, UserRole
from app.repositories.operation_task_repository import OperationTaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.instance_settings import InstanceSettingsUpdate
from app.schemas.pydantic.user import UserCreate, UserUpdate
from app.services.instance_settings_service import InstanceSettingsService
from tests.integration.helpers.instance_settings import wait_runtime
from tests.integration.helpers.names import test_password as password_for
from tests.integration.helpers.names import unique_name
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
        service = instance_settings_service(database, extra_user_token)
        current = service.get()
        updated = service.update(InstanceSettingsUpdate(pu_instance_owner_tg="@owner"))
        assert updated.pu_instance_owner_tg == "@owner"
        wait_runtime("pu_instance_owner_tg", "@owner")
        service.update(InstanceSettingsUpdate(pu_instance_owner_tg=current.pu_instance_owner_tg))
        wait_runtime("pu_instance_owner_tg", current.pu_instance_owner_tg)
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
                UserCreate(
                    login=unique_name("over"),
                    password=password_for("testtest9"),
                )
            )
    finally:
        settings_service.update(
            InstanceSettingsUpdate(pu_instance_user_max_count=current)
        )
        wait_runtime("pu_instance_user_max_count", current)
        _restore_owner(database, repository, extra_user, previous)


def test_user_update_rate(database, cc, extra_user, extra_user_token) -> None:
    repository = UserRepository(database)
    database.expire_all()
    user = repository.get(User(uuid=extra_user.uuid))
    user.last_update_datetime = None
    repository.update(user.uuid, user)

    service = user_service(database, cc, extra_user_token)
    try:
        service.update(UserUpdate(password="password1"))
        with pytest.raises(UserError):
            service.update(UserUpdate(password="password2"))
    finally:
        database.expire_all()
        user = repository.get(User(uuid=extra_user.uuid))
        user.last_update_datetime = None
        repository.update(user.uuid, user)


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
