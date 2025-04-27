from fastapi import Depends
from sqlmodel import Session

from app.dto.agent.abc import Agent
from app.repositories.permission_repository import PermissionRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.auth.auth_service import AuthServiceFactory
from app.services.auth.authorization_service import AuthorizationService
from app.services.utils import token_depends


class AccessService:
    current_agent: Agent
    _is_bot_auth: bool = False

    def __init__(
        self,
        db: Session,
        jwt_token: str = Depends(token_depends),
    ) -> None:
        self.user_repository = UserRepository(db)
        self.unit_repository = UnitRepository(db)
        self.permission_repository = PermissionRepository(db)
        self.auth = AuthServiceFactory(
            self.unit_repository, self.user_repository, jwt_token, self._is_bot_auth
        ).create()
        self.current_agent = self.auth.get_current_agent()
        self.authorization = AuthorizationService(self.permission_repository, self.current_agent)
