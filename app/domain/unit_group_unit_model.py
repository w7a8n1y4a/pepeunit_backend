import uuid as uuid_pkg

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class UnitGroupUnit(SQLModel, table=True):
    """Unit membership in a visual group. One unit can sit in many groups."""

    __tablename__ = "mtm_unit_groups_units"
    __table_args__ = (
        UniqueConstraint(
            "unit_group_uuid",
            "unit_uuid",
            name="mtm_unit_groups_units_pair_key",
        ),
    )

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    unit_group_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                "unit_groups.uuid",
                name="mtm_unit_groups_units_unit_group_uuid_fkey",
                ondelete="CASCADE",
            ),
            nullable=False,
        )
    )
    unit_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                "units.uuid",
                name="mtm_unit_groups_units_unit_uuid_fkey",
                ondelete="CASCADE",
            ),
            nullable=False,
            index=True,
        )
    )
