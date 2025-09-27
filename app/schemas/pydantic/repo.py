import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel

from app.dto.enum import OrderByDate, VisibilityLevel


class PlatformRead(BaseModel):
    name: str
    link: str


class RepoRead(BaseModel):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    default_branch: str | None = None
    is_auto_update_repo: bool
    default_commit: str | None = None
    is_only_tag_update: bool

    is_compilable_repo: bool

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID

    repository_registry_uuid: uuid_pkg.UUID


class ReposResult(BaseModel):
    count: int
    repos: list[RepoRead]


class TargetVersionRead(BaseModel):
    commit: str
    tag: str | None = None


class RepoCreate(BaseModel):
    repository_registry_uuid: uuid_pkg.UUID
    default_branch: str

    visibility_level: VisibilityLevel
    name: str

    is_compilable_repo: bool


class RepoUpdate(BaseModel):
    visibility_level: VisibilityLevel | None = None
    name: str | None = None

    is_auto_update_repo: bool | None = None

    default_branch: str | None = None
    default_commit: str | None = None

    is_only_tag_update: bool | None = None

    is_compilable_repo: bool | None = None


@dataclass
class RepoFilter:
    repository_registry_uuid: uuid_pkg.UUID | None = None

    uuids: list[uuid_pkg.UUID] | None = Query([])

    creator_uuid: uuid_pkg.UUID | None = None
    creators_uuids: list[uuid_pkg.UUID] | None = Query([])
    search_string: str | None = None

    is_auto_update_repo: bool | None = None

    visibility_level: list[str] | None = Query(
        [item.value for item in VisibilityLevel]
    )

    order_by_create_date: OrderByDate | None = OrderByDate.desc
    order_by_last_update: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    def dict(self):
        return self.__dict__


class RepoVersionRead(BaseModel):
    commit: str
    unit_count: int
    tag: str | None = None


class RepoVersionsRead(BaseModel):
    unit_count: int
    versions: list[RepoVersionRead]
