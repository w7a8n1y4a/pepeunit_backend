import datetime
import uuid as uuid_pkg
from dataclasses import dataclass

from pydantic import BaseModel

from app.dto.enum import (
    DashboardPanelTypeEnum,
    DashboardStatus,
    DatasourceFormat,
    OrderByDate,
)
from app.schemas.pydantic.shared import UnitNodeRead
from app.utils.utils import parse_interval


@dataclass
class DatasourceFilter:
    format: DatasourceFormat

    start_agg_datetime: datetime.datetime | None = None
    end_agg_datetime: datetime.datetime | None = None

    start_create_datetime: datetime.datetime | None = None
    end_create_datetime: datetime.datetime | None = None

    relative_time: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    @property
    def relative_interval(self):
        return (
            parse_interval(self.relative_time) if self.relative_time else None
        )

    def dict(self):
        return self.__dict__


class DatasourceTimeSeriesData(BaseModel):
    time: int
    value: str | float | dict


@dataclass
class DashboardFilter:
    search_string: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    def dict(self):
        return self.__dict__


@dataclass
class DashboardPanelFilter:
    dashboard_uuid: uuid_pkg.UUID | None = None

    search_string: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    def dict(self):
        return self.__dict__


class DashboardCreate(BaseModel):
    name: str


class DashboardPanelCreate(BaseModel):
    dashboard_uuid: uuid_pkg.UUID

    title: str
    type: DashboardPanelTypeEnum


class LinkUnitNodeToPanel(BaseModel):
    unit_node_uuid: uuid_pkg.UUID
    dashboard_panels_uuid: uuid_pkg.UUID
    is_last_data: bool
    is_forced_to_json: bool


class DashboardRead(BaseModel):
    uuid: uuid_pkg.UUID
    grafana_uuid: uuid_pkg.UUID

    name: str
    create_datetime: datetime.datetime

    dashboard_url: str | None = None
    inc_last_version: int | None = None

    sync_status: DashboardStatus | None = None
    sync_error: str | None = None
    sync_last_datetime: datetime.datetime | None = None

    creator_uuid: uuid_pkg.UUID


class DashboardsResult(BaseModel):
    count: int
    dashboards: list[DashboardRead]


class UnitNodeForPanel(BaseModel):
    unit_node: UnitNodeRead
    is_last_data: bool
    is_forced_to_json: bool
    unit_with_unit_node_name: str


class DashboardPanelRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: DashboardPanelTypeEnum

    title: str
    create_datetime: datetime.datetime

    creator_uuid: uuid_pkg.UUID
    dashboard_uuid: uuid_pkg.UUID

    unit_nodes_for_panel: list[UnitNodeForPanel]


class DashboardPanelsResult(BaseModel):
    count: int
    panels: list[DashboardPanelRead]
