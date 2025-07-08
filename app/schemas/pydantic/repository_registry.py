import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Query
from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import BaseModel

from app.dto.enum import CredentialStatus, GitPlatform, OrderByDate, RepositoryRegistryStatus


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
    credentials: Optional[Credentials] = None


class RepositoryRegistryRead(BaseModel):
    uuid: uuid_pkg.UUID

    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    releases_data: Optional[str] = None

    local_repository_size: int

    sync_status: Optional[RepositoryRegistryStatus] = None
    sync_error: Optional[str] = None
    sync_last_datetime: Optional[datetime] = None

    create_datetime: datetime
    last_update_datetime: datetime

    creator_uuid: Optional[uuid_pkg.UUID] = None

    branches: list[str]


@dataclass
class RepositoryRegistryFilter:
    uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    creator_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    is_public_repository: Optional[bool] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__


class CommitRead(BaseModel):
    commit: str
    summary: str
    tag: Optional[str] = None


class CommitFilter(Filter):
    repo_branch: str
    only_tag: bool = False

    offset: Optional[int] = 0
    limit: Optional[int] = 10
