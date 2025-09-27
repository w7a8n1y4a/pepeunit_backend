import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class DashboardPanel(SQLModel, table=True):
    """
    Сущность панелей внутри dashboard
    """

    __tablename__ = "dashboard_panels"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # type visualisation, Heatmap, Histogram, Stat
    type: str = Field(nullable=False)
    # visualization name
    title: str = Field(nullable=False)

    create_datetime: datetime = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("users.uuid", ondelete="CASCADE")
        )
    )
    dashboard_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("dashboards.uuid", ondelete="CASCADE"),
        )
    )
