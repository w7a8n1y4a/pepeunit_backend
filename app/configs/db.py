from contextlib import contextmanager

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, create_engine

from app import settings

engine = create_engine(
    settings.sqlalchemy_database_url,
    echo=settings.backend_debug,
    echo_pool=settings.backend_debug,
    future=True,
    json_serializer=jsonable_encoder,
    pool_pre_ping=True,
    pool_size=max(5, settings.backend_worker_count * 2),
    max_overflow=max(5, settings.backend_worker_count),
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
