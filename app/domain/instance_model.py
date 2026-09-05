import uuid as uuid_pkg
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.dto.enum import InstanceTrustStatus


class Instance(SQLModel, table=True):
    """External Pepeunit instance"""

    __tablename__ = "instances"

    # Instance uuid
    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # Unique URL to GET .../instances/current
    url: str = Field(nullable=False, unique=True)

    # Instance trust status
    trust_status: str = Field(
        nullable=False,
        default=InstanceTrustStatus.PENDING,
    )

    # Last Instance response time in milliseconds
    last_ping: float | None = Field(nullable=True)

    # Last Instance collection status
    last_collection_status: str = Field(nullable=True)

    # Last successful Instance collection datetime
    last_success_datetime: datetime = Field(nullable=True)

    # Last Instance collection attempt datetime
    last_attempt_datetime: datetime = Field(nullable=True)

    # Number of consecutive successful collections
    consecutive_success_count: int = Field(nullable=False, default=0, ge=0)

    # Last Instance collection error
    last_collection_error: str = Field(nullable=True, max_length=256)

    # Last collected Instance state
    state: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=True),
    )

    # Instance creation datetime
    create_datetime: datetime = Field(nullable=False)
