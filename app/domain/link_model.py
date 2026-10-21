import uuid as uuid_pkg

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class Link(SQLModel, table=True):
    """
    Link between different UnitIO

    output -> input
    """

    __tablename__ = "links"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # routed output UnitIO
    output_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("units_io.uuid", ondelete="CASCADE"),
        )
    )
    # target input UnitIO
    input_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("units_io.uuid", ondelete="CASCADE"),
        )
    )
    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("users.uuid", ondelete="CASCADE")
        )
    )
