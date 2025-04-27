from fastapi import Depends

from app.dto.agent.abc import Agent
from app.repositories.permission_repository import PermissionRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services.auth.auth_service import AuthServiceFactory
from app.services.auth.authorization_service import AuthorizationService
from app.services.utils import token_depends


class AccessService:
    current_agent: Agent

    def __init__(
        self,
        permission_repository: PermissionRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        jwt_token: str = Depends(token_depends),
        is_bot_auth: bool = False,
    ) -> None:
        self.user_repository = user_repository
        self.unit_repository = unit_repository
        self.permission_repository = permission_repository
        self.auth = AuthServiceFactory(self.unit_repository, self.user_repository, jwt_token, is_bot_auth).create()
        self.current_agent = self.auth.get_current_agent()
        self.authorization = AuthorizationService(permission_repository, self.current_agent)
