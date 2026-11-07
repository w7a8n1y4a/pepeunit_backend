import datetime
import re
import uuid as uuid_pkg
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, field_validator

from app.dto.enum import (
    DashboardPanelTypeEnum,
    DashboardStatus,
    DatasourceFormat,
    OrderByDate,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin
from app.schemas.pydantic.shared import UnitIORead
from app.utils.utils import parse_interval


@dataclass
class DatasourceFilter(BasePaginationRestMixin):
    format: DatasourceFormat

    start_agg_datetime: datetime.datetime | None = None
    end_agg_datetime: datetime.datetime | None = None

    start_create_datetime: datetime.datetime | None = None
    end_create_datetime: datetime.datetime | None = None

    relative_time: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

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
class DashboardFilter(BasePaginationRestMixin):
    search_string: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    def dict(self):
        return self.__dict__


@dataclass
class DashboardPanelFilter(BasePaginationRestMixin):
    dashboard_uuid: uuid_pkg.UUID | None = None

    search_string: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    def dict(self):
        return self.__dict__


class DashboardCreate(BaseModel):
    name: str


class DashboardPanelCreate(BaseModel):
    dashboard_uuid: uuid_pkg.UUID

    title: str
    type: DashboardPanelTypeEnum


class LinkUnitIOToPanel(BaseModel):
    unit_io_uuid: uuid_pkg.UUID
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


class UnitIOForPanel(BaseModel):
    unit_io: UnitIORead
    is_last_data: bool
    is_forced_to_json: bool
    unit_with_unit_io_name: str


class DashboardPanelRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: DashboardPanelTypeEnum

    title: str
    create_datetime: datetime.datetime

    creator_uuid: uuid_pkg.UUID
    dashboard_uuid: uuid_pkg.UUID

    unit_ios_for_panel: list[UnitIOForPanel]


class DashboardPanelsResult(BaseModel):
    count: int
    panels: list[DashboardPanelRead]


class GrafanaLoginTicketCreate(BaseModel):
    root_path: ClassVar[str] = "/grafana/"
    path_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"^/grafana/[A-Za-z0-9\-._~%/?=&:,+@!$*;]*$"
    )

    path: str | None = None

    @field_validator("path")
    @classmethod
    def path_stays_in_grafana(cls, value: str | None) -> str | None:
        if not value:
            return None
        path = value.split("?", 1)[0]
        if (
            not cls.path_pattern.fullmatch(value)
            or "//" in path
            or ".." in path.split("/")
        ):
            msg = f"path must stay under {cls.root_path}"
            raise ValueError(msg)
        return value


class GrafanaLoginTicketRead(BaseModel):
    ticket: str
    expires_in: int
