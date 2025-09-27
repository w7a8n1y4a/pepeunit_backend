import uuid as uuid_pkg

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class UnitNodeEdge(SQLModel, table=True):
    """
    Связь разных UnitNode

    output -> input
    """

    __tablename__ = "units_nodes_edges"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4
    )

    # routed output UnitNode
    node_output_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("units_nodes.uuid", ondelete="CASCADE")
        )
    )
    # target input UnitNode
    node_input_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("units_nodes.uuid", ondelete="CASCADE")
        )
    )
    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("users.uuid", ondelete="CASCADE")
        )
    )
