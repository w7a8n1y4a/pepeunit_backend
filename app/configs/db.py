import json
import logging
import threading
from contextlib import contextmanager, suppress

import psycopg2
import psycopg2.extensions
from fastapi.encoders import jsonable_encoder
from sqlalchemy import event
from sqlmodel import Session, create_engine

from app import settings


class _ConnGate:
    """Tracks driver calls on one socket.

    A Python lock around execute does not keep the pool from taking the
    connection: Session.close() resets the session, checkin runs on
    another thread, and psycopg2 drops the GIL inside PQexec. Rollback
    then reads the SELECT that is still on the socket (PGRES_TUPLES_OK).
    Checkin waits until every other thread has left the driver.
    """

    def __init__(self) -> None:
        self.libpq = threading.RLock()
        self._calls = threading.Condition(threading.Lock())
        self._threads: dict[int, int] = {}

    def begin(self) -> None:
        ident = threading.get_ident()
        with self._calls:
            self._threads[ident] = self._threads.get(ident, 0) + 1

    def end(self) -> None:
        ident = threading.get_ident()
        with self._calls:
            left = self._threads.get(ident, 0) - 1
            if left > 0:
                self._threads[ident] = left
            else:
                self._threads.pop(ident, None)
            self._calls.notify_all()

    def wait_for_others(self) -> None:
        ident = threading.get_ident()
        with self._calls:
            while any(thread != ident for thread in self._threads):
                self._calls.wait()


class _GuardingCursor(psycopg2.extensions.cursor):
    def _call(self, fn, *args, **kwargs):
        gate = self.connection._conn_gate
        gate.begin()
        try:
            with gate.libpq:
                return fn(*args, **kwargs)
        finally:
            gate.end()

    def execute(self, *args, **kwargs):
        return self._call(super().execute, *args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._call(super().executemany, *args, **kwargs)

    def callproc(self, *args, **kwargs):
        return self._call(super().callproc, *args, **kwargs)

    def fetchone(self, *args, **kwargs):
        return self._call(super().fetchone, *args, **kwargs)

    def fetchmany(self, *args, **kwargs):
        return self._call(super().fetchmany, *args, **kwargs)

    def fetchall(self, *args, **kwargs):
        return self._call(super().fetchall, *args, **kwargs)

    def scroll(self, *args, **kwargs):
        return self._call(super().scroll, *args, **kwargs)

    def copy_expert(self, *args, **kwargs):
        return self._call(super().copy_expert, *args, **kwargs)

    def copy_to(self, *args, **kwargs):
        return self._call(super().copy_to, *args, **kwargs)

    def copy_from(self, *args, **kwargs):
        return self._call(super().copy_from, *args, **kwargs)

    def close(self):
        return self._call(super().close)


class _GuardingConnection(psycopg2.extensions.connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._conn_gate = _ConnGate()
        self.cursor_factory = _GuardingCursor

    def cursor(self, *args, **kwargs):
        kwargs["cursor_factory"] = _GuardingCursor
        return super().cursor(*args, **kwargs)

    def _return_to_pool(self, fn):
        gate = self._conn_gate
        gate.wait_for_others()
        with gate.libpq:
            return fn()

    def commit(self):
        return self._return_to_pool(super().commit)

    def rollback(self):
        gate = self._conn_gate
        gate.wait_for_others()
        with gate.libpq:
            try:
                return super().rollback()
            except psycopg2.DatabaseError as exc:
                if "PGRES_TUPLES_OK" not in str(exc):
                    raise
                logging.error(
                    "Rollback found a pending query result; "
                    "closing the connection"
                )
                with suppress(psycopg2.Error):
                    super().close()
                raise

    def close(self):
        return self._return_to_pool(super().close)

    def cancel(self):
        return self._return_to_pool(super().cancel)

    def reset(self):
        return self._return_to_pool(super().reset)

    def set_session(self, *args, **kwargs):
        gate = self._conn_gate
        gate.wait_for_others()
        with gate.libpq:
            return super().set_session(*args, **kwargs)

    def set_isolation_level(self, *args, **kwargs):
        gate = self._conn_gate
        gate.wait_for_others()
        with gate.libpq:
            return super().set_isolation_level(*args, **kwargs)

    def set_client_encoding(self, *args, **kwargs):
        gate = self._conn_gate
        gate.wait_for_others()
        with gate.libpq:
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


@event.listens_for(engine.pool, "reset")
def _wait_out_driver_calls(dbapi_connection, _record, _reset_state) -> None:
    if dbapi_connection is not None:
        dbapi_connection._conn_gate.wait_for_others()


def _session() -> Session:
    # close() must not leave the session able to check out another connection.
    return Session(engine, close_resets_only=False)


def get_session() -> Session:
    with _session() as session:
        yield session


@contextmanager
def get_hand_session() -> Session:
    with _session() as session:
        yield session
