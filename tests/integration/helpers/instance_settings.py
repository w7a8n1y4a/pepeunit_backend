import time
from contextlib import contextmanager

from app import runtime
from app.configs.runtime import Runtime
from app.domain.user_model import User
from app.schemas.pydantic.instance_settings import InstanceSettingsUpdate
from tests.integration.helpers.owner import as_owner
from tests.integration.helpers.services import instance_settings_service


def wait_runtime(name: str, value) -> None:
    deadline = time.monotonic() + Runtime.REFRESH_SECONDS + 1
    while time.monotonic() < deadline:
        if getattr(runtime.get(), name) == value:
            return
        time.sleep(0.25)
    actual = getattr(runtime.get(), name)
    msg = f"{name} is {actual}, expected {value}"
    raise AssertionError(msg)


@contextmanager
def owner_setting(database, user: User, token: str, name: str, value):
    with as_owner(database, user):
        service = instance_settings_service(database, token)
        original = getattr(service.get(), name)
        service.update(InstanceSettingsUpdate(**{name: value}))
        wait_runtime(name, value)
        try:
            yield
        finally:
            service.update(InstanceSettingsUpdate(**{name: original}))
            wait_runtime(name, original)
