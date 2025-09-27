import uuid as uuid_pkg
from abc import ABC
from datetime import datetime, timedelta
from typing import Optional

import jwt
from pydantic import BaseModel, Field

from app import settings
from app.configs.errors import NoAccessError
from app.domain.unit_model import Unit
from app.domain.user_model import User
from app.dto.enum import AgentStatus, AgentType, UserRole


class Agent(ABC, BaseModel):
    uuid: uuid_pkg.UUID
    name: str
    type: AgentType
    status: AgentStatus
    role: Optional[UserRole] = None
    panel_uuid: Optional[uuid_pkg.UUID] = None

    def generate_agent_token(self, access_token_exp: Optional[int] = None) -> str:
        if not access_token_exp:
            access_token_exp = datetime.utcnow() + timedelta(
                seconds=settings.backend_auth_token_expiration
            )

        if self.type == AgentType.USER:
            token = jwt.encode(
                {"uuid": str(self.uuid), "type": self.type, "exp": access_token_exp},
                settings.backend_secret_key,
                "HS256",
            )
        elif self.type == AgentType.UNIT:
            token = jwt.encode(
                {"uuid": str(self.uuid), "type": self.type},
                settings.backend_secret_key,
                "HS256",
            )
        elif self.type == AgentType.BACKEND:
            token = jwt.encode(
                {"domain": settings.backend_domain, "type": self.type},
                settings.backend_secret_key,
                "HS256",
            )
        elif self.type == AgentType.GRAFANA:
            token = jwt.encode(
                {"uuid": str(self.uuid), "type": self.type, "exp": access_token_exp},
                settings.backend_secret_key,
                "HS256",
            )
        elif self.type == AgentType.GRAFANA_UNIT_NODE:
            token = jwt.encode(
                {
                    "uuid": str(self.uuid),
                    "panel_uuid": str(self.panel_uuid),
                    "type": self.type,
                },
                settings.backend_secret_key,
                "HS256",
            )
        else:
            raise NoAccessError("Unknown agent type")

        return token


class AgentUser(Agent, User):
    type: AgentType = AgentType.USER

    def __init__(self, **data):
        super().__init__(**data)
        self.name = self.login


class AgentUnit(Agent, Unit):
    type: AgentType = AgentType.UNIT
    status: AgentStatus = AgentStatus.VERIFIED


class AgentBot(Agent):
    uuid: uuid_pkg.UUID = uuid_pkg.uuid4()
    name: str = "bot"
    status: AgentStatus = AgentStatus.UNVERIFIED
    type: AgentType = AgentType.BOT


class AgentBackend(Agent):
    uuid: Optional[uuid_pkg.UUID] = Field(
        default_factory=lambda: uuid_pkg.uuid5(
            uuid_pkg.NAMESPACE_DNS, settings.backend_domain
        )
    )
    type: AgentType = AgentType.BACKEND
    status: AgentStatus = AgentStatus.VERIFIED


class AgentGrafana(Agent):
    type: AgentType = AgentType.GRAFANA
    status: AgentStatus = AgentStatus.VERIFIED


class AgentGrafanaUnitNode(Agent):
    type: AgentType = AgentType.GRAFANA_UNIT_NODE
    status: AgentStatus = AgentStatus.VERIFIED
