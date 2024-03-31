from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, create_engine

from app import settings


engine = create_engine(
    settings.sqlalchemy_database_url, echo=settings.debug, future=True, json_serializer=jsonable_encoder, pool_pre_ping=True
)


def get_session() -> Session:
    with Session(engine) as session:
        yield session
