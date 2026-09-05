import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel, Field, JsonValue

from app import settings
from app.dto.enum import (
    GitPlatform,
    InstanceCollectionStatus,
    InstanceTrustStatus,
    IntegrationTestsStatus,
)
from app.schemas.pydantic.pagination import BasePaginationRestMixin
from app.schemas.pydantic.shared import FeatureFlags


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
    last_collection_error: str | None
    state: dict[str, JsonValue] | None
    create_datetime: datetime


@dataclass
class InstanceFilter(BasePaginationRestMixin):
    trust_status: list[str] | None = Query(
        [item.value for item in InstanceTrustStatus]
    )

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


class CurrentInstanceSettingsV1(BaseModel):
    pu_state_send_interval: int = settings.pu_state_send_interval
    pu_max_external_repo_size: int = settings.pu_max_external_repo_size
    pu_max_cipher_length: int = settings.pu_max_cipher_length
    pu_unit_log_expiration: int = settings.pu_unit_log_expiration
    pu_max_pagination_size: int = settings.pu_max_pagination_size
    pu_mqtt_max_clients: int = settings.pu_mqtt_max_clients
    pu_mqtt_max_client_connection_rate: str = (
        settings.pu_mqtt_max_client_connection_rate
    )
    pu_mqtt_max_client_id_len: int = settings.pu_mqtt_max_client_id_len
    pu_mqtt_client_max_messages_rate: str = (
        settings.pu_mqtt_client_max_messages_rate
    )
    pu_mqtt_client_max_bytes_rate: str = settings.pu_mqtt_client_max_bytes_rate
    pu_mqtt_max_payload_size: int = settings.pu_mqtt_max_payload_size
    pu_mqtt_max_qos: int = settings.pu_mqtt_max_qos
    pu_mqtt_max_topic_levels: int = settings.pu_mqtt_max_topic_levels
    pu_mqtt_max_len_message_queue: int = settings.pu_mqtt_max_len_message_queue
    pu_mqtt_max_topic_alias: int = settings.pu_mqtt_max_topic_alias


class CurrentInstanceStateV1(BaseModel):
    instance_datetime: datetime
    integration_tests_datetime: datetime | None = None
    integration_tests_status: IntegrationTestsStatus | None = None
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
    email: str = settings.pu_admin_email
    telegram: str = settings.pu_admin_tg


class CurrentInstanceSchemaV1(BaseModel):
    schema_version: Literal["v1"] = "v1"
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    swagger: str = f"{settings.pu_link_prefix}/docs"
    graphql: str = f"{settings.pu_link_prefix}/graphql"
    grafana: str = f"{settings.pu_link}/grafana/"
    telegram_bot: str = settings.pu_telegram_bot_link
    feature_flags: FeatureFlags = FeatureFlags()
    settings: CurrentInstanceSettingsV1 = CurrentInstanceSettingsV1()
    state: CurrentInstanceStateV1
    metrics: CurrentInstanceMetricsV1
    contacts: CurrentInstanceContactsV1 = CurrentInstanceContactsV1()
