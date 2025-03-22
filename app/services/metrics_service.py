from cachetools import TTLCache
from fastapi import Depends

from app.repositories.enum import AgentType
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.metrics import BaseMetricsRead
from app.services.access_service import AccessService

cache = TTLCache(maxsize=1, ttl=600)


class MetricsService:

    def __init__(
        self,
        repo_repository: RepoRepository = Depends(),
        unit_node_edge_repository: UnitNodeEdgeRepository = Depends(),
        unit_node_repository: UnitNodeRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        access_service: AccessService = Depends(),
    ) -> None:
        self.repo_repository = repo_repository
        self.unit_repository = unit_repository
        self.unit_node_repository = unit_node_repository
        self.unit_node_edge_repository = unit_node_edge_repository
        self.user_repository = user_repository
        self.access_service = access_service

    def get_instance_metrics(self) -> BaseMetricsRead:
        cache_key = "instance_metrics"

        if cache_key in cache:
            return cache[cache_key]

        self.access_service.authorization.check_access([AgentType.BOT, AgentType.USER, AgentType.UNIT])

        metrics = BaseMetricsRead(
            user_count=self.user_repository.get_all_count(),
            repo_count=self.repo_repository.get_all_count(),
            unit_count=self.unit_repository.get_all_count(),
            unit_node_count=self.unit_node_repository.get_all_count(),
            unit_node_edge_count=self.unit_node_edge_repository.get_all_count(),
        )

        cache[cache_key] = metrics

        return metrics
