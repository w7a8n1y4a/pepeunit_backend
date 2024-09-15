import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.repositories.enum import VisibilityLevel


class UnitNode(SQLModel, table=True):
    """
    Представление состояния input или output топика Unit
    """

    __tablename__ = 'units_nodes'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # Input or Output
    type: str = Field(nullable=False)

    visibility_level: str = Field(nullable=False, default=VisibilityLevel.PUBLIC)
    # if is_rewritable_input = False - no Unit can set a value for this UnitNode
    is_rewritable_input: bool = Field(nullable=False, default=False)

    # linked topic name
    topic_name: str = Field(nullable=False)
    create_datetime: datetime = Field(nullable=False, default_factory=datetime.utcnow)

    # last state topic - only for topics with prefix #/pepeunit
    state: str = Field(nullable=True)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
    # to Unit link
    unit_uuid: uuid_pkg.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE')))
