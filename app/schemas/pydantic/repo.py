import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from fastapi_filter.contrib.sqlalchemy import Filter

from app.repositories.enum import VisibilityLevel, OrderByDate


class RepoRead(BaseModel):
    """Экземпляр репозитория"""

    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    repo_url: str
    is_public_repository: bool
    is_credentials_set: bool

    default_branch: Optional[str] = None
    is_auto_update_repo: bool
    update_frequency_in_seconds: int
    last_update_datetime: datetime

    branches: list[str]

    creator_uuid: uuid_pkg.UUID


class Credentials(BaseModel):
    """Данные для доступа к удалённым репозиториям"""

    username: str
    pat_token: str


class CommitRead(BaseModel):
    """Данные о коммите"""

    commit: str
    summary: str
    tag: Optional[str] = None


class RepoCreate(BaseModel):
    """Создание репозитория"""

    visibility_level: VisibilityLevel
    name: str

    repo_url: str

    is_public_repository: bool
    credentials: Optional[Credentials] = None

    is_auto_update_repo: bool
    update_frequency_in_seconds: Optional[int] = 86400


class RepoUpdate(BaseModel):
    """Обновление данных репозитория"""

    visibility_level: VisibilityLevel
    name: str

    is_public_repository: bool

    is_auto_update_repo: bool
    update_frequency_in_seconds: int


class RepoFilter(Filter):
    """Фильтр выборки репозиториев"""

    search_string: Optional[str] = Field(description="descr text")

    is_public_repository: Optional[bool] = None
    is_auto_update_repo: Optional[bool] = None

    visibility_level: Optional[VisibilityLevel] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None


class CommitFilter(Filter):
    """Фильтр выборки коммитов"""

    repo_branch: str

    offset: Optional[int] = 0
    limit: Optional[int] = 10
