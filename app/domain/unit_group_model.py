import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.domain.icon_model import Icon


class UnitGroup(SQLModel, table=True):
    """Visual group of units. A user sees only groups they created."""

    __tablename__ = "unit_groups"
    __table_args__ = (
        UniqueConstraint(
            "creator_uuid",
            "name",
            name="unit_groups_creator_name_key",
        ),
    )

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # Default picture is generated from the group uuid.
    icon_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                Icon.__table__.c.uuid,
                name="unit_groups_icon_uuid_fkey",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    # Unique for the creator
    name: str = Field(nullable=False)
    create_datetime: datetime = Field(nullable=False)

    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                "users.uuid",
                name="unit_groups_creator_uuid_fkey",
                ondelete="CASCADE",
            ),
            nullable=False,
        )
    )
