import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.dto.enum import GitPlatform, RepositoryRegistryStatus
from app.dto.repository_registry import Credentials


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
