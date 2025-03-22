from abc import ABC, abstractmethod
from typing import Optional

import jwt

from app import settings
from app.configs.errors import NoAccessError
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.agent.abc import Agent, AgentBackend, AgentBot, AgentUnit, AgentUser
from app.repositories.enum import AgentStatus, AgentType, UserStatus
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository


class AuthService(ABC):

    @abstractmethod
    def get_current_agent(self) -> Agent:
        pass

    @staticmethod
    def generate_agent_token(agent: Agent) -> str:
        return jwt.encode({"uuid": str(agent.uuid), "type": agent.type}, settings.backend_secret_key, "HS256")


class JwtAuthService(AuthService):

    def __init__(
        self,
        user_repo: UserRepository,
        unit_repo: UnitRepository,
        jwt_token: Optional[str],
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
            data = jwt.decode(self.jwt_token, settings.backend_secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise NoAccessError("Token expired")
        except jwt.InvalidTokenError:
            raise NoAccessError("Token is invalid")

        return self._get_agent_from_token(data)

    def _get_agent_from_token(self, data):
        agent = None
        if data.get("type") == AgentType.USER:
            user = self.user_repo.get(User(uuid=data["uuid"]))
            if user:
                agent = AgentUser(**user.dict())

        elif data.get("type") == AgentType.UNIT:
            unit = self.unit_repo.get(Unit(uuid=data["uuid"]))
            if unit:
                agent = AgentUnit(**unit.dict())

        elif data.get("type") == AgentType.BACKEND:
            agent = AgentBackend(name=data['domain'], status=AgentStatus.VERIFIED)

        else:
            raise NoAccessError("Invalid agent type")

        if not agent or agent.status == AgentStatus.BLOCKED:
            raise NoAccessError("Agent is blocked or not found")

        return agent

    def get_current_agent(self) -> Agent:
        return self.current_agent


class TgBotAuthService(AuthService):

    def __init__(
        self,
        user_repo: UserRepository,
        unit_repo: UnitRepository,
        telegram_chat_id: Optional[str],
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
        agent = AgentUser(**user.dict())

        if not agent:
            raise NoAccessError("User not found")

        if agent.status == UserStatus.BLOCKED:
            raise NoAccessError("User is Blocked")

        return agent

    def get_current_agent(self) -> Agent:
        return self.current_agent


class AuthServiceFactory:
    def __init__(
        self, unit_repo: UnitRepository, user_repo: UserRepository, jwt_token: str, is_bot_auth: bool = False
    ) -> None:
        self.user_repository = user_repo
        self.unit_repository = unit_repo
        self.jwt_token = jwt_token
        self.is_bot_auth = is_bot_auth

    def create(self) -> AuthService:
        if self.is_bot_auth:
            return TgBotAuthService(self.user_repository, self.unit_repository, self.jwt_token)
        else:
            return JwtAuthService(self.user_repository, self.unit_repository, self.jwt_token)
