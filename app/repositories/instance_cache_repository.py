import threading
from dataclasses import dataclass

from app.schemas.gql.inputs.instance import InstanceFilterInput
from app.schemas.pydantic.instance import (
    CurrentInstanceSchemaV1,
    InstanceFilter,
    InstancePublicRegistry,
    InstanceRead,
    InstanceRegistriesPage,
    InstancesPage,
    InstanceUrlsPage,
)


@dataclass(frozen=True)
class InstanceCacheSnapshot:
    current: CurrentInstanceSchemaV1
    instances: tuple[InstanceRead, ...]
    urls: tuple[str, ...]
    registries: tuple[InstancePublicRegistry, ...]


class InstanceCacheRepository:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot: InstanceCacheSnapshot | None = None

    def update(self, snapshot: InstanceCacheSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def get_current(self) -> CurrentInstanceSchemaV1:
        with self._lock:
            return self._get_snapshot().current

    def get_instances(
        self,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> InstancesPage:
        with self._lock:
            instances = self._get_snapshot().instances
            return InstancesPage(
                total_count=len(instances),
                instances=self._slice(instances, filters),
            )

    def get_urls(
        self,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> InstanceUrlsPage:
        with self._lock:
            urls = self._get_snapshot().urls
            return InstanceUrlsPage(
                total_count=len(urls),
                urls=self._slice(urls, filters),
            )

    def get_registries(
        self,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> InstanceRegistriesPage:
        with self._lock:
            registries = self._get_snapshot().registries
            return InstanceRegistriesPage(
                total_count=len(registries),
                registries=self._slice(registries, filters),
            )

    def _get_snapshot(self) -> InstanceCacheSnapshot:
        if self._snapshot is None:
            msg = "Instance cache is not initialized"
            raise RuntimeError(msg)
        return self._snapshot

    @staticmethod
    def _slice(
        items: tuple,
        filters: InstanceFilter | InstanceFilterInput,
    ) -> list:
        offset = filters.offset or 0
        if filters.limit:
            return list(items[offset : offset + filters.limit])
        return list(items[offset:])
