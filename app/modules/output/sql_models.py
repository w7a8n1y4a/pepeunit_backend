import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.repositories.enum import VisibilityLevel


class UnitOutput(SQLModel, table=True):
    """Представление выходящей переменной Unit"""

    __tablename__ = 'units_outputs'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # уровень видимости для пользователей
    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC.value)

    # название топика output переменной
    topic_name: str = Field(nullable=False)
    # время создания Output
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # последнее состояние Output переменной
    last_state: str = Field(nullable=True)

    # родительский Unit
    unit_uuid: uuid_pkg.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE')))
