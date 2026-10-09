import uuid as uuid_pkg
from datetime import datetime
from typing import Any

from sqlalchemy import Column, ForeignKey, String, Text
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

    # One line for lists and the telegram push. Cut by the notification
    # setting, which stays within this column.
    small_text: str | None = Field(
        default=None,
        max_length=96,
        sa_column=Column(String(96), nullable=True),
    )

    # Monospace table. Null while the row waits or the payload is invalid.
    table_text: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )

    # Raw log. Empty until a notification type has one to show.
    big_text: str | None = Field(
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
