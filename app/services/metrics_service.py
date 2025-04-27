from typing import Optional

from cachetools import TTLCache
from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.dto.enum import AgentType
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.metrics import BaseMetricsRead
from app.services.access_service import AccessService

cache = TTLCache(maxsize=1, ttl=600)


class MetricsService:

    def __init__(self, db: Session = Depends(get_session), jwt_token: Optional[str] = None) -> None:
        self.repo_repository = RepoRepository(db)
        self.unit_repository = UnitRepository(db)
        self.unit_node_repository = UnitNodeRepository(db)
        self.unit_node_edge_repository = UnitNodeEdgeRepository(db)
        self.user_repository = UserRepository(db)
        self.access_service = AccessService(db, jwt_token)

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
