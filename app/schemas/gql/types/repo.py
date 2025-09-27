import uuid as uuid_pkg
from datetime import datetime

import strawberry
from strawberry import field

from app.dto.enum import VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class PlatformType(TypeInputMixin):
    name: str
    link: str


@strawberry.type()
class RepoType(TypeInputMixin):
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


@strawberry.type()
class ReposResultType(TypeInputMixin):
    count: int
    repos: list[RepoType] = field(default_factory=list)


@strawberry.type()
class CommitType(TypeInputMixin):
    commit: str
    summary: str
    tag: str | None = None


@strawberry.type()
class TargetVersionType(TypeInputMixin):
    commit: str
    tag: str | None = None


@strawberry.type()
class RepoVersionType(TypeInputMixin):
    commit: str
    unit_count: int
    tag: str | None = None


@strawberry.type()
class RepoVersionsType(TypeInputMixin):
    unit_count: int
    versions: list[RepoVersionType]
