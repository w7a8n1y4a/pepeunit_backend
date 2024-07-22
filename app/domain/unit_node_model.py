import uuid as pkg_uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field

from app.repositories.enum import VisibilityLevel


class UnitNode(SQLModel, table=True):
    """
    Представление состояния input или output топика Unit
    """

    __tablename__ = 'units_nodes'

    uuid: pkg_uuid.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=pkg_uuid.uuid4)

    # Input or Output
    type: str = Field(nullable=False)

    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC.value)
    # if is_rewritable_input = False - no Unit can set a value for this UnitNode
    is_rewritable_input: bool = Field(nullable=False, default=False)

    # linked topic name
    topic_name: str = Field(nullable=False)
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # last state topic - only for topics with prefix #/pepeunit
    state: str = Field(nullable=True)

    # to User link
    creator_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
    # to Unit link
    unit_uuid: pkg_uuid.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE')))
