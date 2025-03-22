import uuid as uuid_pkg
from abc import ABC
from typing import Optional

from pydantic import BaseModel

from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.enum import AgentStatus, AgentType, UserRole


class Agent(BaseModel, ABC):
    uuid: uuid_pkg.UUID
    name: str
    type: AgentType
    status: AgentStatus
    role: Optional[UserRole] = None


class AgentUser(Agent, User, BaseModel):
    type: AgentType = AgentType.USER

    @property
    def name(self) -> str:
        return self.login


class AgentUnit(Agent, Unit, BaseModel):
    type: AgentType = AgentType.UNIT
    status: AgentStatus = AgentStatus.VERIFIED


class AgentBot(Agent, BaseModel):
    uuid: uuid_pkg.UUID = uuid_pkg.uuid4()
    name: str = 'bot'
    status: AgentStatus = AgentStatus.UNVERIFIED
    type: AgentType = AgentType.BOT


class AgentBackend(Agent, BaseModel):
    type: AgentType = AgentType.BACKEND
    status: AgentStatus = AgentStatus.VERIFIED

    @property
    def uuid(self) -> uuid_pkg.UUID:
        namespace = uuid_pkg.NAMESPACE_DNS
        return uuid_pkg.uuid5(namespace, self.name)
