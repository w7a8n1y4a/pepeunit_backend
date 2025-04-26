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
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
)


def get_session() -> Session:
    session = Session(engine)
    try:
        yield session
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
