import uuid as uuid_pkg
from datetime import datetime
from typing import Any

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


class Notification(SQLModel, table=True):
    """Notification addressed to one user"""

    __tablename__ = "notifications"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    create_datetime: datetime = Field(nullable=False)

    # What the notification shows
    type: str = Field(nullable=False)

    # Arbitrary payload of the notification
    data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
    )

    is_read: bool = Field(nullable=False, default=False)

    read_datetime: datetime = Field(nullable=True)

    # to User link
    target_user_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.uuid", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
