import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry

from app.repositories.enum import VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class RepoType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    visibility_level: VisibilityLevel

    name: str
    create_datetime: datetime

    repo_url: str
    is_public_repository: bool

    default_branch: Optional[str] = None
    is_auto_update_repo: bool
    default_commit: Optional[str] = None
    is_only_tag_update: bool

    last_update_datetime: datetime

    branches: list[str]

    creator_uuid: uuid_pkg.UUID


@strawberry.type()
class CommitType(TypeInputMixin):
    commit: str
    summary: str
    tag: Optional[str] = None


@strawberry.type()
class RepoVersionType(TypeInputMixin):
    commit: str
    unit_count: int
    tag: Optional[str] = None


@strawberry.type()
class RepoVersionsType(TypeInputMixin):
    unit_count: int
    versions: list[RepoVersionType]
