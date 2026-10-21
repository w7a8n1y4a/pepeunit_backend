import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, JsonValue

from app.dto.enum import GitPlatform, PeerCollectionStatus, PeerTrustStatus
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class PeerCreate(BaseModel):
    url: str


class PeerUpdate(BaseModel):
    trust_status: PeerTrustStatus


class PeerRead(BaseModel):
    uuid: uuid_pkg.UUID
    url: str
    trust_status: PeerTrustStatus
    last_ping: float | None
    last_collection_status: PeerCollectionStatus | None
    last_success_datetime: datetime | None
    last_attempt_datetime: datetime | None
    consecutive_success_count: int
    last_collection_error: str | None
    state: dict[str, JsonValue] | None
    create_datetime: datetime


@dataclass
class PeerFilter(BasePaginationRestMixin):
    trust_status: list[str] | None = Query(
        [item.value for item in PeerTrustStatus]
    )

    def dict(self):
        return self.__dict__


class PeersPage(BaseModel):
    total_count: int
    peers: list[PeerRead]


class PeerUrlsPage(BaseModel):
    total_count: int
    urls: list[str]


class PeerPublicRepo(BaseModel):
    url: str
    platform: GitPlatform


class PeerReposPage(BaseModel):
    total_count: int
    repos: list[PeerPublicRepo]
