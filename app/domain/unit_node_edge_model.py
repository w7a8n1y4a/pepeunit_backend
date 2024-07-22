import uuid as pkg_uuid

from sqlalchemy import ForeignKey, Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import SQLModel, Field


class UnitNodeEdge(SQLModel, table=True):
    """
    Связь разных UnitNode

    output -> input
    """

    __tablename__ = 'units_nodes_edges'

    uuid: pkg_uuid.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=pkg_uuid.uuid4)

    # routed output UnitNode
    node_output_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units_nodes.uuid', ondelete='CASCADE'))
    )
    # target input UnitNode
    node_input_uuid: pkg_uuid.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units_nodes.uuid', ondelete='CASCADE'))
    )
