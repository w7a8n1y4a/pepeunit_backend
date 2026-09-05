import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.dto.enum import OperationTaskStatus


class OperationTask(SQLModel, table=True):
    """Manual user operation task"""

    __tablename__ = "operation_tasks"

    # OperationTask uuid
    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # OperationTask creation datetime
    create_datetime: datetime = Field(nullable=False)

    # OperationTask start datetime
    start_datetime: datetime = Field(nullable=True)

    # OperationTask finish datetime
    finish_datetime: datetime = Field(nullable=True)

    # OperationTask execution status
    status: str = Field(
        nullable=False,
        default=OperationTaskStatus.RUNNING,
    )

    # OperationTask execution result, can keep a full test log
    result: str = Field(nullable=True)

    # OperationTask type
    task_type: str = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.uuid", ondelete="CASCADE"),
            nullable=False,
        ),
    )
