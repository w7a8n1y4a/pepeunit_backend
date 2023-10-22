import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.core.enum import VisibilityLevel


class UnitInput(SQLModel, table=True):
    """Представление входящей переменной Unit"""

    __tablename__ = 'units_inputs'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True)

    # уровень видимости для пользователей
    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC.value)
    # переменная перезаписываемая? если False, то никакой другой Unit перезаписать её не сможет, даже с доступом
    is_rewritable_input: bool = Field(nullable=False, default=False)

    # название топика Input переменной
    topic_name: str = Field(nullable=False)
    # время создания Input
    create_datetime: datetime = Field(nullable=False, default=datetime.utcnow())

    # последнее состояние Input переменной
    last_state: str = Field(nullable=True)

    # родительский Unit
    unit_uuid: uuid_pkg.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('unit.uuid', ondelete='CASCADE')))
