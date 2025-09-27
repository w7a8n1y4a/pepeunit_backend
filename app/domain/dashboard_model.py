import uuid as uuid_pkg
from datetime import datetime

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel


class Dashboard(SQLModel, table=True):
    """
    Отвечающая за взаимодействие с grafana, содержит в себе панели
    """

    __tablename__ = "dashboards"

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        index=True,
        default_factory=uuid_pkg.uuid4,
    )

    # uuid in grafana
    grafana_uuid: uuid_pkg.UUID = Field(
        nullable=False, default_factory=uuid_pkg.uuid4
    )
    # dashboard name, user set
    name: str = Field(nullable=False)

    # url from grafana
    dashboard_url: str = Field(nullable=True)
    # number last version from grafana
    inc_last_version: int = Field(nullable=True)

    # last sync status
    sync_status: str = Field(nullable=True)
    # error last sync
    sync_error: str = Field(nullable=True)
    # time last sync
    sync_last_datetime: datetime = Field(nullable=True)

    create_datetime: datetime = Field(nullable=False)

    # to User link
    creator_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True), ForeignKey("users.uuid", ondelete="CASCADE")
        )
    )
