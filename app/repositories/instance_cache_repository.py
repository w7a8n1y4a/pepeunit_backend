import threading
from dataclasses import dataclass
from typing import Any

from app.configs.errors import InstanceError
from app.repositories.utils import resolve_query_default
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
from app.schemas.pydantic.pagination import NO_PAGINATION


@dataclass(frozen=True)
class InstanceCacheSnapshot:
    current: CurrentInstanceSchemaV1
    instances: tuple[InstanceRead, ...]
    urls: tuple[str, ...]
    registries: tuple[InstancePublicRegistry, ...]


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
                raise InstanceError(msg)
            return self._snapshot

    def get_current(self) -> CurrentInstanceSchemaV1:
        return self.get().current

    def get_instances(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> InstancesPage:
        trust_status = resolve_query_default(filters.trust_status) or []
        instances = tuple(
            instance
            for instance in self.get().instances
            if instance.trust_status in trust_status
        )

        count, page = self.apply_offset_and_limit(instances, filters)
        return InstancesPage(total_count=count, instances=page)

    def get_urls(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> InstanceUrlsPage:
        count, page = self.apply_offset_and_limit(self.get().urls, filters)
        return InstanceUrlsPage(total_count=count, urls=page)

    def get_registries(
        self, filters: InstanceFilter | InstanceFilterInput
    ) -> InstanceRegistriesPage:
        count, page = self.apply_offset_and_limit(
            self.get().registries, filters
        )
        return InstanceRegistriesPage(total_count=count, registries=page)

    @staticmethod
    def apply_offset_and_limit(
        items: tuple[Any, ...],
        filters: InstanceFilter | InstanceFilterInput,
    ) -> tuple[int, list]:
        if filters.limit == NO_PAGINATION:
            return len(items), list(items)

        return len(items), list(
            items[filters.offset : filters.offset + filters.limit]
        )


instance_cache = InstanceCacheRepository()
