import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from fastapi_filter.contrib.sqlalchemy import Filter

from app.core.enum import OrderByDate, VisibilityLevel


class UnitRead(BaseModel):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None

    unit_state_dict: Optional[str] = None

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID
    repo_uuid: uuid_pkg.UUID


class UnitCreate(BaseModel):
    repo_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


class UnitUpdate(BaseModel):
    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None


class UnitFilter(Filter):
    search_string: Optional[str] = None

    is_auto_update_from_repo_unit: Optional[bool] = None

    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
