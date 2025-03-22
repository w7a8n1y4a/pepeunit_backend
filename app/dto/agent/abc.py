import uuid as uuid_pkg
from abc import ABC

from pydantic import BaseModel

from app import AgentType
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.repositories.enum import AgentStatus


class Agent(BaseModel, ABC):
    uuid: uuid_pkg.UUID
    name: str
    type: AgentType
    status: AgentStatus


class AgentUser(BaseModel, Agent, User):
    type: AgentType = AgentType.USER

    @property
    def name(self) -> str:
        return self.login


class AgentUnit(BaseModel, Agent, Unit):
    type: AgentType = AgentType.UNIT


class AgentBot(BaseModel, Agent):
    uuid: uuid_pkg.UUID = uuid_pkg.uuid4()
    name: str = 'bot'
    type: AgentType = AgentType.BOT


class AgentBackend(BaseModel, Agent):
    type: AgentType = AgentType.BACKEND

    @property
    def uuid(self) -> uuid_pkg.UUID:
        namespace = uuid_pkg.NAMESPACE_DNS
        return uuid_pkg.uuid5(namespace, self.name)
