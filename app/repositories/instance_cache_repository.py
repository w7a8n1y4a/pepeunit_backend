import threading
from dataclasses import dataclass
from typing import Any

from app.configs.error_codes import ErrorCode
from app.configs.errors import InstanceError
from app.repositories.utils import resolve_query_default
from app.schemas.pydantic.instance import CurrentInstanceSchemaV1
from app.schemas.pydantic.pagination import NO_PAGINATION
from app.schemas.pydantic.peer import (
    PeerFilter,
    PeerPublicRepo,
    PeerRead,
    PeerReposPage,
    PeersPage,
    PeerUrlsPage,
)


@dataclass(frozen=True)
class InstanceCacheSnapshot:
    current: CurrentInstanceSchemaV1
    peers: tuple[PeerRead, ...]
    urls: tuple[str, ...]
    repos: tuple[PeerPublicRepo, ...]


class InstanceCacheRepository:
    """Public instance state prepared for serving"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot: InstanceCacheSnapshot | None = None

    def update(self, snapshot: InstanceCacheSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def get(self) -> InstanceCacheSnapshot:
        with self._lock:
            if self._snapshot is None:
                msg = "Instance cache is not initialized"
                raise InstanceError(
                    msg, code=ErrorCode.INSTANCE_CACHE_NOT_INITIALIZED
                )
            return self._snapshot

    def get_current(self) -> CurrentInstanceSchemaV1:
        return self.get().current

    def get_peers(self, filters: PeerFilter) -> PeersPage:
        trust_status = resolve_query_default(filters.trust_status) or []
        peers = tuple(
            peer
            for peer in self.get().peers
            if peer.trust_status in trust_status
        )

        count, page = self.apply_offset_and_limit(peers, filters)
        return PeersPage(total_count=count, peers=page)

    def get_urls(self, filters: PeerFilter) -> PeerUrlsPage:
        count, page = self.apply_offset_and_limit(self.get().urls, filters)
        return PeerUrlsPage(total_count=count, urls=page)

    def get_repos(self, filters: PeerFilter) -> PeerReposPage:
        count, page = self.apply_offset_and_limit(self.get().repos, filters)
        return PeerReposPage(total_count=count, repos=page)

    @staticmethod
    def apply_offset_and_limit(
        items: tuple[Any, ...],
        filters: PeerFilter,
    ) -> tuple[int, list]:
        if filters.limit == NO_PAGINATION:
            return len(items), list(items)

        return len(items), list(
            items[filters.offset : filters.offset + filters.limit]
        )


instance_cache = InstanceCacheRepository()
