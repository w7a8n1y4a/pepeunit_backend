import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app import settings
from app.repositories.enum import UnitNodeTypeEnum, VisibilityLevel


class Root(BaseModel):
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    authors: list = settings.authors
    swagger: str = f'{settings.backend_link_prefix}/docs'
    graphql: str = f'{settings.backend_link_prefix}/graphql'
    telegram_bot: str = settings.telegram_bot_link


class MqttRead(BaseModel):
    result: str


class UnitNodeRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    topic_name: str

    create_datetime: datetime
    state: Optional[str] = None

    unit_uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID


class UnitNodesResult(BaseModel):
    count: int
    unit_nodes: list[UnitNodeRead]
