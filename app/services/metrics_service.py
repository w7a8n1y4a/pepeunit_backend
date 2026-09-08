from cachetools import TTLCache
from fastapi import Depends

from app.dto.enum import AgentType, CacheKey
from app.repositories.repo_repository import RepoRepository
from app.repositories.repository_registry_repository import (
    RepositoryRegistryRepository,
)
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.metrics import BaseMetricsRead
from app.schemas.pydantic.repository_registry import RepositoryRegistryFilter
from app.services.access_service import AccessService


class MetricsService:
    _cache = TTLCache(maxsize=2, ttl=600)

    def __init__(
        self,
        repository_registry_repository: RepositoryRegistryRepository = Depends(),
        repo_repository: RepoRepository = Depends(),
        unit_node_edge_repository: UnitNodeEdgeRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repository_registry_repository = repository_registry_repository
        self.repo_repository = repo_repository
        self.unit_repository = unit_repository
        self.unit_node_repository = unit_node_repository
        self.unit_node_edge_repository = unit_node_edge_repository
        self.user_repository = user_repository
        self.access_service = access_service

    def get_instance_metrics(
        self,
        is_api: bool = True,
        public_only: bool = False,
    ) -> BaseMetricsRead:
        if is_api:
            self.access_service.authorization.check_access(
                [AgentType.BOT, AgentType.USER, AgentType.UNIT]
            )

        cache_key = (
            CacheKey.INSTANCE_METRICS_PUBLIC
            if public_only
            else CacheKey.INSTANCE_METRICS
        )

        if cache_key in self._cache:
            return self._cache[cache_key]

        if public_only:
            metrics = BaseMetricsRead(
                user_count=self.user_repository.get_all_count(),
                repository_registry_count=self.repository_registry_repository.list(
                    RepositoryRegistryFilter(
                        is_public_repository=True,
                        limit=0,
                    )
                )[0],
                repo_count=self.repo_repository.get_public_count(),
                unit_count=self.unit_repository.get_public_count(),
                unit_node_count=self.unit_node_repository.get_public_count(),
                unit_node_edge_count=(
                    self.unit_node_edge_repository.get_public_count()
                ),
            )
        else:
            metrics = BaseMetricsRead(
                user_count=self.user_repository.get_all_count(),
                repository_registry_count=self.repository_registry_repository.get_all_count(),
                repo_count=self.repo_repository.get_all_count(),
                unit_count=self.unit_repository.get_all_count(),
                unit_node_count=self.unit_node_repository.get_all_count(),
                unit_node_edge_count=self.unit_node_edge_repository.get_all_count(),
            )

        self._cache[cache_key] = metrics

        return metrics
