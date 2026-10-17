"""Per-process copy of the instance_settings row.

Each gunicorn worker has its own object. The lock is local to this process.
The row is reloaded from Postgres every 5 seconds.
"""

import threading
import time

from app.domain.instance_settings_model import InstanceSettings


class Runtime:
    REFRESH_SECONDS = 5

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._row: InstanceSettings | None = None
        self._loaded_at = 0.0

    def get(self) -> InstanceSettings:
        with self._lock:
            fresh = self._row is not None and (
                time.monotonic() - self._loaded_at < self.REFRESH_SECONDS
            )
            if fresh:
                return self._row

            self._row = self._read()
            self._loaded_at = time.monotonic()
            return self._row

    def invalidate(self) -> None:
        with self._lock:
            self._row = None
            self._loaded_at = 0.0

    @staticmethod
    def _read() -> InstanceSettings:
        from app.configs.db import get_hand_session
        from app.repositories.instance_settings_repository import (
            InstanceSettingsRepository,
        )

        with get_hand_session() as db:
            row = InstanceSettingsRepository(db).get(
                InstanceSettings(uuid=InstanceSettings.ROW_UUID)
            )
            if row is None:
                msg = "instance_settings row is missing"
                raise RuntimeError(msg)
            payload = row.model_dump()
        return InstanceSettings.model_validate(payload)


runtime = Runtime()
