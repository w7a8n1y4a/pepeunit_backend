import time
from collections.abc import Callable

import pytest


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
