import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class PanelsUnitNodes(SQLModel, table=True):
    """
    MtM панелей и UnitNode
    """

    __tablename__ = 'mtm_panels_unit_nodes'

    uuid: uuid_pkg.UUID = Field(primary_key=True, nullable=False, index=True, default_factory=uuid_pkg.uuid4)

    # only the latest values regardless of the data type calculated based on DataPipe config
    is_last_data: bool = Field(nullable=False, default=False)

    create_datetime: datetime = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('users.uuid', ondelete='CASCADE'))
    )
    unit_node_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('units_nodes.uuid', ondelete='CASCADE'))
    )
    dashboard_panels_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(UUID(as_uuid=True), ForeignKey('dashboard_panels.uuid', ondelete='CASCADE'))
    )
