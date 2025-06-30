from typing import Optional

from pydantic import BaseModel

from app.dto.enum import GitPlatform


class Credentials(BaseModel):
    username: str
    pat_token: str


class RepositoryRegistryCreate(BaseModel):
    platform: GitPlatform
    repository_url: str

    is_public_repository: bool
    credentials: Optional[Credentials] = None
