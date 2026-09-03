import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    JsonValue,
)

from app.dto.enum import (
    GitPlatform,
    InstanceCollectionStatus,
    InstanceTrustStatus,
    IntegrationTestsStatus,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin


class InstanceCreate(BaseModel):
    url: str


class InstanceUpdate(BaseModel):
    trust_status: InstanceTrustStatus


class InstanceRead(BaseModel):
    uuid: uuid_pkg.UUID
    url: str
    trust_status: InstanceTrustStatus
    last_ping: float | None
    last_collection_status: InstanceCollectionStatus | None
    last_success_datetime: datetime | None
    last_attempt_datetime: datetime | None
    consecutive_success_count: int
    last_collection_error: Annotated[str | None, Field(max_length=256)]
    state: dict[str, JsonValue] | None
    create_datetime: datetime


@dataclass
class InstanceFilter(BasePaginationRestMixin):
    def dict(self):
        return self.__dict__


class InstancesPage(BaseModel):
    total_count: int
    instances: list[InstanceRead]


class InstanceUrlsPage(BaseModel):
    total_count: int
    urls: list[str]


class InstancePublicRegistry(BaseModel):
    url: str
    platform: GitPlatform


class InstanceRegistriesPage(BaseModel):
    total_count: int
    registries: list[InstancePublicRegistry]


class CurrentInstanceFeatureFlags(BaseModel):
    pu_ff_telegram_bot_enable: bool
    pu_ff_grafana_integration_enable: bool
    pu_ff_datapipe_enable: bool
    pu_ff_datapipe_default_last_value_enable: bool
    pu_ff_prometheus_enable: bool
    pu_ff_federation_enable: bool


class CurrentInstanceSettingsV1(BaseModel):
    pu_state_send_interval: int
    pu_max_external_repo_size: int
    pu_max_cipher_length: int
    pu_unit_log_expiration: int
    pu_max_pagination_size: int
    pu_mqtt_max_clients: int
    pu_mqtt_max_client_connection_rate: str
    pu_mqtt_max_client_id_len: int
    pu_mqtt_client_max_messages_rate: str
    pu_mqtt_client_max_bytes_rate: str
    pu_mqtt_max_payload_size: int
    pu_mqtt_max_qos: int
    pu_mqtt_max_topic_levels: int
    pu_mqtt_max_len_message_queue: int
    pu_mqtt_max_topic_alias: int


class CurrentInstanceStateV1(BaseModel):
    instance_datetime: datetime
    integration_tests_datetime: datetime | None
    integration_tests_status: IntegrationTestsStatus | None
    integration_tests_success_percentage: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class CurrentInstanceMetricsV1(BaseModel):
    user_count: int = Field(ge=0)
    repository_registry_count: int = Field(ge=0)
    repo_count: int = Field(ge=0)
    unit_count: int = Field(ge=0)
    unit_node_count: int = Field(ge=0)
    unit_node_edge_count: int = Field(ge=0)


class CurrentInstanceContactsV1(BaseModel):
    email: str = ""
    telegram: str = ""


class CurrentInstanceSchemaV1(BaseModel):
    schema_version: Literal["v1"] = "v1"
    name: str
    version: str
    description: str
    license: str
    swagger: str
    graphql: str
    grafana: str
    telegram_bot: str
    feature_flags: CurrentInstanceFeatureFlags
    settings: CurrentInstanceSettingsV1
    state: CurrentInstanceStateV1
    metrics: CurrentInstanceMetricsV1
    contacts: CurrentInstanceContactsV1
