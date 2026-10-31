import json
import os
from contextlib import contextmanager

from fastapi.encoders import jsonable_encoder
from sqlalchemy import event
from sqlmodel import Session, create_engine

from app import settings

_LOST_SYNC = "lost synchronization with server"

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
)


def _drop_inherited_pool() -> None:
    # close=False does not write on the parent's socket. Closing it in
    # the child sends Terminate on the same libpq connection.
    engine.dispose(close=False)


# Gunicorn forks the master. A pool created before that fork must not
# be reused: every worker would share one Postgres backend.
os.register_at_fork(after_in_child=_drop_inherited_pool)


@event.listens_for(engine, "handle_error")
def _drop_desynced_connection(context) -> None:
    original = context.original_exception
    if original is not None and _LOST_SYNC in str(original):
        context.is_disconnect = True


def get_session() -> Session:
    with Session(engine) as session:
        yield session


@contextmanager
def get_hand_session() -> Session:
    with Session(engine) as session:
        yield session
