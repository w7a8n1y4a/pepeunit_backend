import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from fastapi_filter.contrib.sqlalchemy import Filter

from app.core.enum import OrderByDate, VisibilityLevel
from app.modules.unit.examples import ex_unit_read, ex_unit_create, ex_unit_update


class UnitRead(BaseModel):
    """Экземпляр Unit"""

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

    # только для создателя Unit - т.к. внутри архива всегда лежит ещё и .env файл
    unit_program_url: Optional[str] = None

    class Config:
        schema_extra = {"example": ex_unit_read}


class UnitCreate(BaseModel):
    """Создание Unit"""

    repo_uuid: uuid_pkg.UUID

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None

    class Config:
        schema_extra = {"example": ex_unit_create}


class UnitUpdate(BaseModel):
    """Обновление данных репозитория"""

    visibility_level: VisibilityLevel
    name: str

    is_auto_update_from_repo_unit: bool

    repo_branch: Optional[str] = None
    repo_commit: Optional[str] = None

    class Config:
        schema_extra = {"example": ex_unit_update}


class UnitFilter(Filter):
    """Фильтр выборки репозиториев"""

    search_string: Optional[str] = Field(description="descr text")

    is_auto_update_from_repo_unit: Optional[bool] = None

    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
