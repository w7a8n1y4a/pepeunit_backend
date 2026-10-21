import uuid as uuid_pkg
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.dto.enum import PeerTrustStatus


class Peer(SQLModel, table=True):
    """External Pepeunit peer"""

    __tablename__ = "peers"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # Unique URL to GET .../instances/current
    url: str = Field(nullable=False, unique=True)

    trust_status: str = Field(
        nullable=False,
        default=PeerTrustStatus.PENDING,
    )

    # Last response time in milliseconds
    last_ping: float | None = Field(nullable=True)

    last_collection_status: str = Field(nullable=True)

    last_success_datetime: datetime = Field(nullable=True)

    last_attempt_datetime: datetime = Field(nullable=True)

    # Number of consecutive successful collections
    consecutive_success_count: int = Field(nullable=False, default=0, ge=0)

    last_collection_error: str = Field(nullable=True, max_length=256)

    # Last collected current-instance state
    state: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=True),
    )

    create_datetime: datetime = Field(nullable=False)
