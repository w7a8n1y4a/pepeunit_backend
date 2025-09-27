import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import BaseModel

from app.dto.enum import (
    CredentialStatus,
    GitPlatform,
    OrderByDate,
    RepositoryRegistryStatus,
)


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
class RepositoryRegistryFilter:
    uuids: list[uuid_pkg.UUID] | None = Query([])

    creator_uuid: uuid_pkg.UUID | None = None
    search_string: str | None = None

    is_public_repository: bool | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    def dict(self):
        return self.__dict__


class CommitRead(BaseModel):
    commit: str
    summary: str
    tag: str | None = None


class CommitFilter(Filter):
    repo_branch: str
    only_tag: bool = False

    offset: int | None = 0
    limit: int | None = 10
