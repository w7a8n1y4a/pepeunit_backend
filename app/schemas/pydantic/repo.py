import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import GitPlatform, OrderByDate, VisibilityLevel


class RepoRead(BaseModel):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    default_branch: Optional[str] = None
    is_auto_update_repo: bool
    default_commit: Optional[str] = None
    is_only_tag_update: bool

    is_compilable_repo: bool

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID

    repository_registry_uuid: uuid_pkg.UUID


class ReposResult(BaseModel):
    count: int
    repos: list[RepoRead]


class Credentials(BaseModel):
    username: str
    pat_token: str


class TargetVersionRead(BaseModel):
    commit: str
    tag: Optional[str] = None


class PlatformRead(BaseModel):
    name: str
    link: str


class RepoCreate(BaseModel):
    visibility_level: VisibilityLevel
    name: str

    repository_url: str
    platform: GitPlatform

    is_public_repository: bool
    credentials: Optional[Credentials] = None

    is_compilable_repo: bool


class RepoUpdate(BaseModel):
    visibility_level: Optional[VisibilityLevel] = None
    name: Optional[str] = None

    is_auto_update_repo: Optional[bool] = None

    default_branch: Optional[str] = None
    default_commit: Optional[str] = None

    is_only_tag_update: Optional[bool] = None

    is_compilable_repo: Optional[bool] = None


@dataclass
class RepoFilter:
    repository_registry_uuid: Optional[uuid_pkg.UUID] = None

    uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    creator_uuid: Optional[uuid_pkg.UUID] = None
    creators_uuids: Optional[list[uuid_pkg.UUID]] = Query([])
    search_string: Optional[str] = None

    is_auto_update_repo: Optional[bool] = None

    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc
    order_by_last_update: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    def dict(self):
        return self.__dict__


class RepoVersionRead(BaseModel):
    commit: str
    unit_count: int
    tag: Optional[str] = None


class RepoVersionsRead(BaseModel):
    unit_count: int
    versions: list[RepoVersionRead]
