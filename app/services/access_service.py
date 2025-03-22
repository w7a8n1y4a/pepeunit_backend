import uuid as uuid_pkg
from datetime import datetime, timedelta
from typing import Optional, Union

import jwt
from fastapi import Depends, params

from app import settings
from app.configs.errors import NoAccessError
from app.domain.permission_model import Permission, PermissionBaseType
from app.domain.repo_model import Repo
from app.domain.unit_model import Unit
from app.domain.unit_node_edge_model import UnitNodeEdge
from app.domain.unit_node_model import UnitNode
from app.domain.user_model import User
from app.dto.agent.abc import Agent
from app.repositories.enum import AgentType, PermissionEntities, UserRole, UserStatus, VisibilityLevel
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
        permission_repository: PermissionRepository = Depends(),
        unit_repository: UnitRepository = Depends(),
        user_repository: UserRepository = Depends(),
        jwt_token: str = Depends(token_depends),
    ) -> None:
        self.user_repository = user_repository
        self.unit_repository = unit_repository
        self.permission_repository = permission_repository
        self.auth = AuthServiceFactory(self.unit_repository, self.user_repository, jwt_token).create()
        self.current_agent = self.auth.get_current_agent()
        self.authorization = AuthorizationService(permission_repository, self.current_agent)

    def access_check(self, available_user_role: list[UserRole], is_unit_available: bool = False):
        """
        Checks the available roles for each of the agent types
        """

        if isinstance(self.current_agent, User):
            if self.current_agent.role not in [role.value for role in available_user_role]:
                raise NoAccessError("The current user role is not in the list of available roles")
        elif isinstance(self.current_agent, Unit):
            if not is_unit_available:
                raise NoAccessError("The resource is not available for the current Unit")
        else:
            raise NoAccessError("Agent unavailable")

    def access_creator_check(self, obj: Union[Repo, Unit, UnitNode, UnitNodeEdge]) -> None:
        if self.current_agent.uuid != obj.creator_uuid:
            raise NoAccessError(
                "Agent {} is not creator this entity - {}.".format(
                    self.current_agent.__class__.__name__, obj.__class__.__name__
                )
            )

    def access_unit_check(self, unit: Unit) -> None:
        if isinstance(self.current_agent, Unit) and unit.uuid != self.current_agent.uuid:
            raise NoAccessError("The unit requesting the information does not have access to it")

    def access_only_creator_and_target_unit(self, unit: Unit):
        if isinstance(self.current_agent, User):
            self.access_creator_check(unit)
        self.access_unit_check(unit)

    def check_access_unit_to_input_node(self, unit_node: UnitNode) -> None:
        """
        Checks that the Unit has access to set the value of the Input UnitNode
        """
        if isinstance(self.current_agent, Unit) and not unit_node.is_rewritable_input:
            raise NoAccessError(
                'This UnitNode topic can only be edited by a User, set is_rewritable_input=True for available'
            )

    def visibility_check(self, check_entity):
        """
        For single entities, defines access by visibility
        """

        if check_entity.visibility_level == VisibilityLevel.PUBLIC:
            pass
        elif check_entity.visibility_level == VisibilityLevel.INTERNAL:
            if not (isinstance(self.current_agent, Unit) or self.current_agent.role in [UserRole.USER, UserRole.ADMIN]):
                raise NoAccessError("Internal visibility level is not allowed")
        elif check_entity.visibility_level == VisibilityLevel.PRIVATE:
            permission_check = PermissionBaseType(
                agent_type=self.current_agent.__class__.__name__,
                agent_uuid=self.current_agent.uuid,
                resource_type=check_entity.__class__.__name__,
                resource_uuid=check_entity.uuid,
            )
            if not self.permission_repository.check(permission_check):
                raise NoAccessError("Private visibility level is not allowed")

    def get_available_visibility_levels(
        self, levels: list[str], restriction: list[str] = None
    ) -> list[VisibilityLevel]:
        """
        Prohibits all external users from getting information about internal entities and cuts off
        Private entities if the agent does not have any records about them
        """

        if not isinstance(self.current_agent, Unit) and self.current_agent.role == UserRole.BOT:
            return [VisibilityLevel.PUBLIC]
        else:
            if restriction:
                return levels
            else:
                return [VisibilityLevel.PUBLIC, VisibilityLevel.INTERNAL]

    def access_restriction(self, resource_type: Optional[PermissionEntities] = None) -> list[uuid_pkg]:
        """
        Allows to get the uuid of all entities to which the agent has access
        """
        return [
            item.resource_uuid
            for item in self.permission_repository.get_agent_resources(
                PermissionBaseType(
                    agent_type=self.current_agent.__class__.__name__,
                    agent_uuid=self.current_agent.uuid,
                    resource_type=resource_type,
                )
            )
        ]

    @staticmethod
    def generate_user_token(user: User) -> str:
        access_token_exp = datetime.utcnow() + timedelta(seconds=settings.backend_auth_token_expiration)

        token = jwt.encode(
            {'uuid': str(user.uuid), 'type': AgentType.USER, 'exp': access_token_exp},
            settings.backend_secret_key,
            'HS256',
        )

        return token

    @staticmethod
    def generate_unit_token(unit: Unit) -> str:
        token = jwt.encode(
            {'uuid': str(unit.uuid), 'type': AgentType.UNIT},
            settings.backend_secret_key,
            'HS256',
        )

        return token
