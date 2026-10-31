import json
import threading
from contextlib import contextmanager

import psycopg2.extensions
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, create_engine

from app import settings


def _libpq_lock(connection) -> threading.Lock:
    lock = getattr(connection, "_libpq_lock", None)
    if lock is None:
        lock = threading.Lock()
        connection._libpq_lock = lock
    return lock


class _GuardingCursor(psycopg2.extensions.cursor):
    """One libpq call at a time on this connection.

    psycopg2 drops the GIL inside execute. Pool checkin runs on another
    thread and would roll the same socket back while that call is still
    in progress, then hand the socket out again. The lock covers the
    whole driver call, so checkin cannot start until the call returns.
    """

    def execute(self, *args, **kwargs):
        with _libpq_lock(self.connection):
            return super().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        with _libpq_lock(self.connection):
            return super().executemany(*args, **kwargs)

    def callproc(self, *args, **kwargs):
        with _libpq_lock(self.connection):
            return super().callproc(*args, **kwargs)

    def copy_expert(self, *args, **kwargs):
        with _libpq_lock(self.connection):
            return super().copy_expert(*args, **kwargs)

    def copy_to(self, *args, **kwargs):
        with _libpq_lock(self.connection):
            return super().copy_to(*args, **kwargs)

    def copy_from(self, *args, **kwargs):
        with _libpq_lock(self.connection):
            return super().copy_from(*args, **kwargs)

    def close(self):
        with _libpq_lock(self.connection):
            return super().close()


class _GuardingConnection(psycopg2.extensions.connection):
    def __init__(self, *args, **kwargs):
        self._libpq_lock = threading.Lock()
        super().__init__(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        kwargs["cursor_factory"] = _GuardingCursor
        return super().cursor(*args, **kwargs)

    def commit(self):
        with self._libpq_lock:
            return super().commit()

    def rollback(self):
        with self._libpq_lock:
            return super().rollback()

    def close(self):
        with self._libpq_lock:
            return super().close()

    def cancel(self):
        with self._libpq_lock:
            return super().cancel()

    def reset(self):
        with self._libpq_lock:
            return super().reset()

    def set_session(self, *args, **kwargs):
        with self._libpq_lock:
            return super().set_session(*args, **kwargs)

    def set_isolation_level(self, *args, **kwargs):
        with self._libpq_lock:
            return super().set_isolation_level(*args, **kwargs)

    def set_client_encoding(self, *args, **kwargs):
        with self._libpq_lock:
            return super().set_client_encoding(*args, **kwargs)


engine = create_engine(
    settings.pu_sqlalchemy_database_url,
    echo=False,
    echo_pool=False,
    future=True,
    json_serializer=lambda data: json.dumps(jsonable_encoder(data)),
    pool_pre_ping=True,
    pool_size=max(5, settings.pu_worker_count * 2),
    max_overflow=max(5, settings.pu_worker_count),
    pool_recycle=1800,
    pool_timeout=10,
    connect_args={"connection_factory": _GuardingConnection},
)


def get_session() -> Session:
    with Session(engine) as session:
        yield session


@contextmanager
def get_hand_session() -> Session:
    with Session(engine) as session:
        yield session
