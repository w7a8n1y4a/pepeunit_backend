import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel, Field

from app import runtime, settings
from app.dto.enum import UnitNodeTypeEnum, VisibilityLevel


class FeatureFlags(BaseModel):
    pu_ff_datapipe_default_last_value_enable: bool
    pu_ff_datapipe_enable: bool
    pu_ff_federation_enable: bool
    pu_ff_grafana_integration_enable: bool
    pu_ff_notification_enable: bool
    pu_ff_prometheus_enable: bool
    pu_ff_telegram_bot_enable: bool

    @classmethod
    def current(cls) -> FeatureFlags:
        return cls(
            pu_ff_datapipe_default_last_value_enable=(
                runtime.get().pu_ff_datapipe_default_last_value_enable
            ),
            pu_ff_datapipe_enable=runtime.get().pu_ff_datapipe_enable,
            pu_ff_federation_enable=runtime.get().pu_ff_federation_enable,
            pu_ff_grafana_integration_enable=(
                runtime.get().pu_ff_grafana_integration_enable
            ),
            pu_ff_notification_enable=runtime.get().pu_ff_notification_enable,
            pu_ff_prometheus_enable=runtime.get().pu_ff_prometheus_enable,
            pu_ff_telegram_bot_enable=runtime.get().pu_ff_telegram_bot_enable,
        )


class Root(BaseModel):
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    authors: list = settings.authors
    swagger: str = f"{settings.pu_link_prefix}/docs"
    grafana: str = f"{settings.pu_link}/grafana/"
    telegram_bot: str = Field(
        default_factory=lambda: runtime.get().pu_telegram_bot_link
    )
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags.current)


class MqttRead(BaseModel):
    result: str


class UnitNodeRead(BaseModel):
    uuid: uuid_pkg.UUID

    type: UnitNodeTypeEnum
    visibility_level: VisibilityLevel

    is_rewritable_input: bool

    max_connections: int

    topic_name: str
    last_update_datetime: datetime

    is_data_pipe_active: bool
    data_pipe_yml: str | None = None
    data_pipe_status: str | None = None
    data_pipe_error: str | None = None

    create_datetime: datetime
    state: str | None = None

    unit_uuid: uuid_pkg.UUID
    creator_uuid: uuid_pkg.UUID


class UnitNodesResult(BaseModel):
    count: int
    unit_nodes: list[UnitNodeRead]
