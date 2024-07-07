from datetime import timedelta, datetime
from http.client import HTTPException
from typing import Optional, Union

import jwt
from fastapi import Depends, params
from fastapi import HTTPException
from fastapi import status as http_status

from app import settings
from app.domain.permission_model import Permission
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.repositories.enum import UserRole, AgentType, VisibilityLevel, UserStatus
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.repositories.permission_repository import PermissionRepository
from app.services.utils import token_depends
from app.services.validators import is_valid_object


class AccessService:
    jwt_token: Optional[str] = None
    current_agent: Optional[Union[User, Unit]] = None
    _is_bot_auth = False

    def __init__(
        self,
        permission_repository: PermissionRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        jwt_token: str = Depends(token_depends),
    ) -> None:
        self.user_repository = user_repository
        self.unit_repository = unit_repository
        self.permission_repository = permission_repository
        self.jwt_token = jwt_token
        self.token_required()

    def token_required(self):

        if not self._is_bot_auth:
            if isinstance(self.jwt_token, params.Depends):
                pass
            elif self.jwt_token is not None:
                try:
                    data = jwt.decode(self.jwt_token, settings.secret_key, algorithms=['HS256'])
                except jwt.exceptions.ExpiredSignatureError:
                    raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
                except jwt.exceptions.InvalidTokenError:
                    raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

                if data['type'] == AgentType.USER.value:
                    agent = self.user_repository.get(User(uuid=data['uuid']))
                    if agent.status == UserStatus.BLOCKED.value:
                        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")
                elif data['type'] == AgentType.UNIT.value:
                    agent = self.unit_repository.get(Unit(uuid=data['uuid']))
                elif data['type'] == AgentType.PEPEUNIT.value:
                    agent = User(role=UserRole.PEPEUNIT.value)

                if not agent:
                    raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

                self.current_agent = agent
            else:
                self.current_agent = User(role=UserRole.BOT.value)

        else:
            if self.jwt_token:
                agent = self.user_repository.get_user_by_credentials(self.jwt_token)
                is_valid_object(agent)

                if agent.status == UserStatus.BLOCKED.value:
                    raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No Access")

                self.current_agent = agent
            else:
                self.current_agent = User(role=UserRole.BOT.value)

    def access_check(self, available_user_role: list[UserRole], is_unit_available: bool = False):

        if isinstance(self.current_agent, User):
            if self.current_agent.role not in [role.value for role in available_user_role]:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
        elif isinstance(self.current_agent, Unit):
            if not is_unit_available:
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")

    def visibility_check(self, check_entity):
        """
        Для одиночных сущностей определяет доступ по видимости
        """

        if check_entity.visibility_level == VisibilityLevel.PUBLIC.value:
            pass
        elif check_entity.visibility_level == VisibilityLevel.INTERNAL.value:
            if not (
                isinstance(self.current_agent, Unit) or
                self.current_agent.role in [UserRole.USER.value, UserRole.ADMIN.value]
            ):
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
        elif check_entity.visibility_level == VisibilityLevel.PRIVATE.value:
            permission_check = Permission(agent_uuid=self.current_agent.uuid, resource_uuid=check_entity.uuid)
            if not self.permission_repository.check(permission_check):
                raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")

    def get_available_visibility_levels(self, levels: list[str], restriction: list[str] = None) -> list[str]:
        """
        Запрещает всем внешним пользователям получать информацию о внутренних сущностях и отсекает
        Приватные сущности, если у агента нет ни одной записи о них
        """

        if self.current_agent.role == UserRole.BOT.value:
            return [VisibilityLevel.PUBLIC.value]
        else:
            if restriction:
                return levels
            else:
                return [VisibilityLevel.PUBLIC.value, VisibilityLevel.INTERNAL]

    def access_restriction(self) -> list[str]:
        """
        Позволяет получить uuid всех сущностей до которых есть доступ у агента
        """
        return self.permission_repository.get_agent_permissions(Permission(agent_uuid=self.current_agent.uuid))

    @staticmethod
    def generate_user_token(user: User) -> str:
        access_token_exp = datetime.utcnow() + timedelta(seconds=int(settings.auth_token_expiration))

        token = jwt.encode(
            {'uuid': str(user.uuid), 'type': AgentType.USER.value, 'exp': access_token_exp},
            settings.secret_key,
            'HS256',
        )

        return token

    @staticmethod
    def generate_unit_token(unit: Unit) -> str:
        token = jwt.encode(
            {'uuid': str(unit.uuid), 'type': AgentType.UNIT.value},
            settings.secret_key,
            'HS256',
        )

        return token

    @staticmethod
    def generate_current_instance_token() -> str:

        token = jwt.encode(
            {'uuid': settings.backend_domain, 'type': AgentType.PEPEUNIT.value},
            settings.secret_key,
            'HS256',
        )

        return token
