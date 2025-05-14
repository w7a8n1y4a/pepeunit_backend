import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.dto.enum import DataPipeStatus, VisibilityLevel


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
    create_datetime: datetime = Field(nullable=False)

    # last state topic - only for topics with prefix #/pepeunit
    state: str = Field(nullable=True)
    last_update_datetime: datetime = Field(nullable=False)

    # pipeline user target state
    is_data_pipe_active: bool = Field(nullable=False, default=False)
    # pipeline data processing config
    data_pipe_yml: str = Field(nullable=True)
    # current pipeline state on worker
    data_pipe_status: str = Field(nullable=True, default=DataPipeStatus.INACTIVE)
    # pipeline error text when status is Error
    data_pipe_error: str = Field(nullable=True)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
    # to Unit link
    unit_uuid: uuid_pkg.UUID = Field(sa_column=Column(UUID(as_uuid=True), ForeignKey('units.uuid', ondelete='CASCADE')))
