import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.dto.enum import GitPlatform, RepositoryRegistryStatus
from app.services.validators import is_valid_json
from app.utils.utils import aes_gcm_decode


class Credentials(BaseModel):
    username: str
    pat_token: str


class RepositoryRegistryCreate(BaseModel):
    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    credentials: Optional[Credentials] = None


class RepositoryRegistryDTO(BaseModel):
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


class RepoWithRepositoryRegistryDTO(BaseModel):
    uuid: uuid_pkg.UUID

    name: str
    create_datetime: datetime

    cipher_credentials_private_repository: Optional[str] = None

    default_branch: Optional[str] = None
    is_auto_update_repo: bool
    default_commit: Optional[str] = None
    is_only_tag_update: bool

    is_compilable_repo: bool

    last_update_datetime: datetime

    creator_uuid: uuid_pkg.UUID

    repository_registry: RepositoryRegistryDTO

    def get_credentials(self) -> Credentials | None:
        return (
            Credentials(
                **is_valid_json(
                    aes_gcm_decode(self.cipher_credentials_private_repository), "cipher creeds private repository"
                )
            )
            if self.cipher_credentials_private_repository
            else None
        )

    def get_physic_path_uuid(self) -> uuid_pkg.UUID:
        if self.repository_registry.is_public_repository:
            return self.repository_registry.uuid
        else:
            return self.uuid
