import uuid as uuid_pkg
from datetime import datetime
from typing import Any

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlmodel import Field, SQLModel


class Notification(SQLModel, table=True):
    """Notification of one user"""

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

    # Whether the user has already read the notification
    is_read: bool = Field(nullable=False, default=False)

    # When the notification was marked as read (null while unread)
    read_datetime: datetime = Field(nullable=True)

    # Base text, filled when the row is processed. Null while it waits
    # or when the payload could not be typed.
    text: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )

    # False until the processing job finishes. Stays false only while the
    # row is waiting, then becomes true even if delivery was skipped.
    is_processed: bool = Field(default=False, nullable=False, index=True)

    # to User link
    user_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.uuid", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    @property
    def creator_uuid(self) -> uuid_pkg.UUID:
        return self.user_uuid
