import uuid as uuid_pkg

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

DEFAULT_SCHEDULED_NOTIFICATION_TIME = "16:00"


class NotificationSettings(SQLModel, table=True):
    """Per-user notification preferences, one row per user"""

    __tablename__ = "notification_settings"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # to User link, one to one
    user_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("users.uuid", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        )
    )

    # Scheduled instance and unit summaries
    is_scheduled_alert_enable: bool = Field(nullable=False, default=True)

    # HH:MM relative to UTC
    scheduled_notification_time: str = Field(
        nullable=False,
        default=DEFAULT_SCHEDULED_NOTIFICATION_TIME,
        max_length=5,
    )

    # All data pipe alerts, the pipe rule itself stays untouched
    is_data_pipe_alert_enable: bool = Field(nullable=False, default=True)

    # Any notification delivered to the telegram bot
    is_telegram_alert_enable: bool = Field(nullable=False, default=True)

    @classmethod
    def for_user(cls, user_uuid: uuid_pkg.UUID) -> NotificationSettings:
        return cls(
            user_uuid=user_uuid,
            is_scheduled_alert_enable=True,
            scheduled_notification_time=DEFAULT_SCHEDULED_NOTIFICATION_TIME,
            is_data_pipe_alert_enable=True,
            is_telegram_alert_enable=True,
        )
