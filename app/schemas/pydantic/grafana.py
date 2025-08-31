import uuid as uuid_pkg
from dataclasses import dataclass
from typing import Optional

from app.dto.enum import OrderByDate


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
