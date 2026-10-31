import json
import threading
from contextlib import contextmanager

import psycopg2.extensions
from fastapi.encoders import jsonable_encoder
from sqlalchemy import event
from sqlmodel import Session, create_engine

from app import settings

# libpq raises this when two commands share one socket. SQLAlchemy does
# not treat it as a disconnect, so the broken connection goes back to
# the pool and the next request fails the same way.
_LOST_SYNC = "lost synchronization with server"


def _run_locked(connection, fn, *args, **kwargs):
    with connection._socket_lock:
        return fn(*args, **kwargs)


class _SerializedCursor(psycopg2.extensions.cursor):
    """One libpq call at a time on this connection.

    ``PQexec`` drops the GIL. Pool checkin runs on another thread and
    would roll the same socket back while that call is still reading.
    Rollback then consumes the SELECT result, and the next read is no
    longer a Postgres message.
    """

    def execute(self, *args, **kwargs):
        return _run_locked(self.connection, super().execute, *args, **kwargs)

    def executemany(self, *args, **kwargs):
        return _run_locked(
            self.connection, super().executemany, *args, **kwargs
        )

    def callproc(self, *args, **kwargs):
        return _run_locked(self.connection, super().callproc, *args, **kwargs)

    def copy_expert(self, *args, **kwargs):
        return _run_locked(
            self.connection, super().copy_expert, *args, **kwargs
        )

    def copy_to(self, *args, **kwargs):
        return _run_locked(self.connection, super().copy_to, *args, **kwargs)

    def copy_from(self, *args, **kwargs):
        return _run_locked(self.connection, super().copy_from, *args, **kwargs)


class _SerializedConnection(psycopg2.extensions.connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._socket_lock = threading.Lock()
        self.cursor_factory = _SerializedCursor

    def cursor(self, *args, **kwargs):
        kwargs["cursor_factory"] = _SerializedCursor
        return super().cursor(*args, **kwargs)

    def commit(self):
        return _run_locked(self, super().commit)

    def rollback(self):
        return _run_locked(self, super().rollback)

    def close(self):
        return _run_locked(self, super().close)

    def reset(self):
        return _run_locked(self, super().reset)

    def set_session(self, *args, **kwargs):
        parent = super().set_session
        return _run_locked(self, parent, *args, **kwargs)

    def set_isolation_level(self, *args, **kwargs):
        parent = super().set_isolation_level
        return _run_locked(self, parent, *args, **kwargs)


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
    connect_args={"connection_factory": _SerializedConnection},
)


@event.listens_for(engine, "handle_error")
def _drop_desynced_connection(context) -> None:
    original = context.original_exception
    if original is not None and _LOST_SYNC in str(original):
        context.is_disconnect = True


def _session() -> Session:
    # A closed session must not check out a fresh connection.
    return Session(engine, close_resets_only=False)


def get_session() -> Session:
    with _session() as session:
        yield session


@contextmanager
def get_hand_session() -> Session:
    with _session() as session:
        yield session
