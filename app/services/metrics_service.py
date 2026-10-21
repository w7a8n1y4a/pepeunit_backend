from cachetools import TTLCache
from fastapi import Depends

from app.dto.enum import AgentType, CacheKey
from app.repositories.link_repository import LinkRepository
from app.repositories.repo_repository import (
    RepoRepository,
)
from app.repositories.unit_io_repository import UnitIORepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.metrics import BaseMetricsRead
from app.schemas.pydantic.repo import RepoFilter
from app.services.access_service import AccessService


class MetricsService:
    _cache = TTLCache(maxsize=2, ttl=600)

    def __init__(
        self,
        repo_repository: RepoRepository = Depends(),
        link_repository: LinkRepository = Depends(),
        unit_io_repository: UnitIORepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repo_repository = repo_repository
        self.unit_repository = unit_repository
        self.unit_io_repository = unit_io_repository
        self.link_repository = link_repository
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
                repo_count=self.repo_repository.list(
                    RepoFilter(
                        is_public_repository=True,
                        limit=0,
                    )
                )[0],
                unit_count=self.unit_repository.get_public_count(),
                unit_io_count=self.unit_io_repository.get_public_count(),
                link_count=self.link_repository.get_public_count(),
            )
        else:
            metrics = BaseMetricsRead(
                user_count=self.user_repository.get_all_count(),
                repo_count=self.repo_repository.get_all_count(),
                unit_count=self.unit_repository.get_all_count(),
                unit_io_count=self.unit_io_repository.get_all_count(),
                link_count=self.link_repository.get_all_count(),
            )

        self._cache[cache_key] = metrics

        return metrics
