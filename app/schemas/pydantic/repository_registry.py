import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import BaseModel, Field

from app import settings
from app.dto.enum import (
    CredentialStatus,
    GitPlatform,
    OrderByDate,
    RepositoryRegistryStatus,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class Credentials(BaseModel):
    username: str
    pat_token: str


class OneRepositoryRegistryCredentials(BaseModel):
    credentials: Credentials
    status: CredentialStatus


class RepositoryRegistryCreate(BaseModel):
    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    credentials: Credentials | None = None


class RepositoryRegistryRead(BaseModel):
    uuid: uuid_pkg.UUID

    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    releases_data: str | None = None

    local_repository_size: int

    sync_status: RepositoryRegistryStatus | None = None
    sync_error: str | None = None
    sync_last_datetime: datetime | None = None

    create_datetime: datetime
    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID | None = None

    branches: list[str]


class RepositoriesRegistryResult(BaseModel):
    count: int
    repositories_registry: list[RepositoryRegistryRead]


@dataclass
class RepositoryRegistryFilter(BasePaginationRestMixin):
    uuids: list[uuid_pkg.UUID] | None = Query([])

    creator_uuid: uuid_pkg.UUID | None = None
    search_string: str | None = None

    is_public_repository: bool | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc

    def dict(self):
        return self.__dict__


class CommitRead(BaseModel):
    commit: str
    summary: str
    tag: str | None = None


class CommitFilter(Filter):
    repo_branch: str
    only_tag: bool = False

    offset: int | None = Field(default=0, ge=0)
    limit: int | None = Field(
        default=10,
        ge=0,
        le=settings.pu_max_pagination_size,
    )
