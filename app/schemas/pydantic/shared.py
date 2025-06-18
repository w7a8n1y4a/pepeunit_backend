import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app import settings
from app.dto.enum import UnitNodeTypeEnum, VisibilityLevel


class Root(BaseModel):
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    authors: list = settings.authors
    swagger: str = f'{settings.backend_link_prefix}/docs'
    graphql: str = f'{settings.backend_link_prefix}/graphql'
    grafana: str = f'{settings.backend_link}/grafana/'
    telegram_bot: str = settings.telegram_bot_link


class MqttRead(BaseModel):
    result: str


class UnitNodeRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    topic_name: str
    last_update_datetime: datetime

    is_data_pipe_active: bool
    data_pipe_yml: Optional[str] = None
    data_pipe_status: Optional[str] = None
    data_pipe_error: Optional[str] = None

    create_datetime: datetime
    state: Optional[str] = None

    unit_uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID


class UnitNodesResult(BaseModel):
    count: int
    unit_nodes: list[UnitNodeRead]
