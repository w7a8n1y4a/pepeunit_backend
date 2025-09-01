import datetime
import uuid as uuid_pkg
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel

from app.dto.enum import DashboardPanelType, DatasourceFormat, OrderByDate
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


@dataclass
class PanelsUnitNodesFilter:
    unit_node_uuid: Optional[uuid_pkg.UUID] = None
    dashboard_panels_uuid: Optional[uuid_pkg.UUID] = None

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
