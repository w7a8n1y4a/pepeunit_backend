from fastapi import Depends

from app.repositories.enum import UserRole
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_edge_repository import UnitNodeEdgeRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.metrics import BaseMetricsRead
from app.services.access_service import AccessService


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
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        return BaseMetricsRead(
            user_count=self.user_repository.get_all_count(),
            unit_count=self.unit_repository.get_all_count(),
            repo_count=self.repo_repository.get_all_count(),
            unit_node_count=self.unit_node_repository.get_all_count(),
            unit_node_edge_count=self.unit_node_edge_repository.get_all_count(),
        )
