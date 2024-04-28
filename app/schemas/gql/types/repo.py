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
    is_credentials_set: bool

    default_branch: Optional[str] = None
    is_auto_update_repo: bool
    update_frequency_in_seconds: int
    last_update_datetime: datetime

    branches: list[str]

    creator_uuid: uuid_pkg.UUID


@strawberry.type()
class CommitType(TypeInputMixin):
    """Данные о коммите"""

    commit: str
    summary: str
    tag: Optional[str] = None
