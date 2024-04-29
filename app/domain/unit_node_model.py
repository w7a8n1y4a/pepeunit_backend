import uuid as pkg_uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.repositories.enum import VisibilityLevel


class UnitNode(SQLModel, table=True):
    """Представление состояния input или output топика Unit"""

    __tablename__ = 'units_nodes'

    uuid: pkg_uuid.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=pkg_uuid.uuid4)

    # определяет тип ноды - input или output
    type: str = Field(nullable=False)

    # уровень видимости для пользователей
    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC.value)
    # переменная перезаписываемая? если False, то никакой другой Unit перезаписать её не сможет, даже с доступом
    is_rewritable_input: bool = Field(nullable=False, default=False)

    # название топика
    topic_name: str = Field(nullable=False)
    # время создания Input
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # последнее состояние топика
    state: str = Field(nullable=True)

    # родительский Unit
    unit_uuid: pkg_uuid.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE')))
