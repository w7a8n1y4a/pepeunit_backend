import datetime
import uuid as uuid_pkg
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from app.dto.enum import DashboardPanelType, DashboardStatus, DatasourceFormat, OrderByDate
from app.utils.utils import parse_interval


@dataclass
class DatasourceFilter:
    format: DatasourceFormat

    time_window_size: Optional[int] = None

    start_agg_datetime: Optional[datetime.datetime] = None
    end_agg_datetime: Optional[datetime.datetime] = None

    start_create_datetime: Optional[datetime.datetime] = None
    end_create_datetime: Optional[datetime.datetime] = None

    relative_time: Optional[str] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    @property
    def relative_interval(self):
        return parse_interval(self.relative_time) if self.relative_time else None

    def dict(self):
        return self.__dict__


class DatasourceTimeseries(BaseModel):
    time: int
    value: float


@dataclass
class DashboardFilter:
    search_string: Optional[str] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__


@dataclass
class DashboardPanelFilter:
    dashboard_uuid: Optional[uuid_pkg.UUID] = None

    search_string: Optional[str] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__


class DashboardCreate(BaseModel):
    name: str


class DashboardPanelCreate(BaseModel):
    dashboard_uuid: uuid_pkg.UUID

    title: str
    type: DashboardPanelType


class LinkUnitNodeToPanel(BaseModel):
    unit_node_uuid: uuid_pkg.UUID
    dashboard_panels_uuid: uuid_pkg.UUID
    is_last_data: bool


class DashboardRead(BaseModel):
    uuid: uuid_pkg.UUID
    grafana_uuid: uuid_pkg.UUID

    name: str
    create_datetime: datetime.datetime

    dashboard_url: Optional[str] = None
    inc_last_version: Optional[int] = None

    sync_status: Optional[DashboardStatus] = None
    sync_error: Optional[str] = None
    sync_last_datetime: Optional[datetime.datetime] = None

    creator_uuid: uuid_pkg.UUID


class DashboardsResult(BaseModel):
    count: int
    dashboards: list[DashboardRead]


class UnitNodeForPanel(BaseModel):
    uuid: uuid_pkg.UUID
    is_last_data: bool
    unit_with_unit_node_name: str


class DashboardPanelsRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: DashboardPanelType

    title: str
    create_datetime: datetime.datetime

    creator_uuid: uuid_pkg.UUID
    dashboard_uuid: uuid_pkg.UUID

    unit_nodes_for_panel: list[UnitNodeForPanel]


class DashboardPanelsResult(BaseModel):
    count: int
    dashboard_panels: list[DashboardPanelsRead]
