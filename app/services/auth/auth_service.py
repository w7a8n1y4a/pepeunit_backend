from abc import ABC, abstractmethod

import jwt

from app import settings
from app.configs.errors import NoAccessError
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.agent.abc import (
    Agent,
    AgentBackend,
    AgentBot,
    AgentGrafana,
    AgentGrafanaUnitNode,
    AgentUnit,
    AgentUser,
)
from app.dto.enum import AgentStatus, AgentType
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository


class AuthService(ABC):
    @abstractmethod
    def get_current_agent(self) -> Agent:
        pass


class JwtAuthService(AuthService):
    def __init__(
        self,
        user_repo: UserRepository,
        unit_repo: UnitRepository,
        jwt_token: str | None,
    ):
        self.user_repo = user_repo
        self.unit_repo = unit_repo
        self.jwt_token = jwt_token
        if jwt_token:
            self.current_agent = self._decode_token()
        else:
            self.current_agent = AgentBot()

    def _decode_token(self):
        if not self.jwt_token:
            return AgentBot
        try:
            data = jwt.decode(
                self.jwt_token,
                settings.backend_secret_key,
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as err:
            msg = "Token expired"
            raise NoAccessError(msg) from err
        except jwt.InvalidTokenError as err:
            msg = "Token is invalid"
            raise NoAccessError(msg) from err

        return self._get_agent_from_token(data)

    def _get_agent_from_token(self, data):
        if data.get("type") == AgentType.USER:
            user = self.user_repo.get(User(uuid=data["uuid"]))
            if user:
                agent = AgentUser(**user.dict())
            else:
                msg = "User not found"
                raise NoAccessError(msg)

        elif data.get("type") == AgentType.UNIT:
            unit = self.unit_repo.get(Unit(uuid=data["uuid"]))
            if unit:
                agent = AgentUnit(**unit.dict())
            else:
                msg = "Unit not found"
                raise NoAccessError(msg)

        elif data.get("type") == AgentType.BACKEND:
            agent = AgentBackend(
                name=data["domain"], status=AgentStatus.VERIFIED
            )

        elif data.get("type") == AgentType.GRAFANA:
            agent = AgentGrafana(uuid=data["uuid"], name="grafana")

        elif data.get("type") == AgentType.GRAFANA_UNIT_NODE:
            agent = AgentGrafanaUnitNode(
                uuid=data["uuid"],
                name="grafana",
                panel_uuid=data["panel_uuid"],
            )

        else:
            msg = "Invalid agent type"
            raise NoAccessError(msg)

        if not agent or agent.status == AgentStatus.BLOCKED:
            msg = "Agent is blocked or not found"
            raise NoAccessError(msg)

        return agent

    def get_current_agent(self) -> Agent:
        return self.current_agent


class TgBotAuthService(AuthService):
    def __init__(
        self,
        user_repo: UserRepository,
        unit_repo: UnitRepository,
        telegram_chat_id: str | None,
    ):
        self.user_repo = user_repo
        self.unit_repo = unit_repo
        self.telegram_chat_id = telegram_chat_id
        if telegram_chat_id:
            self.current_agent = self._get_agent_by_chat_id()
        else:
            self.current_agent = AgentBot()

    def _get_agent_by_chat_id(self):
        user = self.user_repo.get_user_by_credentials(self.telegram_chat_id)

        if user:
            agent = AgentUser(**user.dict())
        else:
            msg = "User not found"
            raise NoAccessError(msg)

        if agent.status == AgentStatus.BLOCKED:
            msg = "User is Blocked"
            raise NoAccessError(msg)

        return agent

    def get_current_agent(self) -> Agent:
        return self.current_agent


class AuthServiceFactory:
    def __init__(
        self,
        unit_repo: UnitRepository,
        user_repo: UserRepository,
        jwt_token: str,
        is_bot_auth: bool = False,
    ) -> None:
        self.user_repository = user_repo
        self.unit_repository = unit_repo
        self.jwt_token = jwt_token
        self.is_bot_auth = is_bot_auth

    def create(self) -> AuthService:
        if self.is_bot_auth:
            return TgBotAuthService(
                self.user_repository, self.unit_repository, self.jwt_token
            )
        return JwtAuthService(
            self.user_repository, self.unit_repository, self.jwt_token
        )
