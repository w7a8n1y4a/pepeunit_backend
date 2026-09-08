import json
from contextlib import contextmanager

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, create_engine

from app import BackendLogLevel, settings

engine = create_engine(
    settings.pu_sqlalchemy_database_url,
    echo=settings.pu_min_log_level == BackendLogLevel.DEBUG,
    echo_pool=settings.pu_min_log_level == BackendLogLevel.DEBUG,
    future=True,
    json_serializer=lambda data: json.dumps(jsonable_encoder(data)),
    pool_pre_ping=True,
    pool_size=max(5, settings.pu_worker_count * 2),
    max_overflow=max(5, settings.pu_worker_count),
    pool_recycle=1800,
    pool_timeout=10,
)


def get_session() -> Session:
    with Session(engine) as session:
        yield session


@contextmanager
def get_hand_session() -> Session:
    with Session(engine) as session:
        yield session
