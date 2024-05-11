
from fastapi import Depends
from sqlmodel import Session

from app.configs.db import get_session
from app.repositories.enum import UserRole
from app.repositories.repo_repository import RepoRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pydantic.metrics import BaseMetricsRead
from app.services.access_service import AccessService
from app.services.utils import token_depends


class MetricsService:
    def __init__(self, db: Session = Depends(get_session), jwt_token: str = Depends(token_depends), is_bot_auth: bool = False) -> None:
        self.unit_repository = UnitRepository(db)
        self.repo_repository = RepoRepository(db)
        self.unit_node_repository = UnitNodeRepository(db)
        self.user_repository = UserRepository(db)
        self.access_service = AccessService(db, jwt_token, is_bot_auth)

    def get_instance_metrics(self) -> BaseMetricsRead:
        self.access_service.access_check([UserRole.BOT, UserRole.USER, UserRole.ADMIN], is_unit_available=True)

        return BaseMetricsRead(
            user_count=self.user_repository.get_all_count(),
            unit_count=self.unit_repository.get_all_count(),
            repo_count=self.repo_repository.get_all_count(),
            unit_node_count=self.unit_node_repository.get_all_count()
        )
