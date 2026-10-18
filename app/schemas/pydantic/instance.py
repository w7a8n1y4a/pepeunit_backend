import uuid as uuid_pkg
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel, Field, JsonValue

from app import runtime, settings
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
    pu_available_name_entity_symbols: str
    pu_available_topic_symbols: str

    pu_datapipe_limit_unit_node_per_one_panel: int

    pu_instance_cipher_max_length: int
    pu_instance_http_connect_timeout: float
    pu_instance_http_timeout: float
    pu_instance_max_pagination_size: int
    pu_instance_max_state_size: int
    pu_instance_registry_max_size: int
    pu_instance_registry_min_interval_sync: int
    pu_instance_retention_days: int
    pu_instance_unit_log_expiration: int
    pu_instance_unit_state_send_interval: int
    pu_instance_user_auth_token_expiration: int

    pu_mqtt_client_max_bytes_rate: str
    pu_mqtt_client_max_messages_rate: str
    pu_mqtt_host: str
    pu_mqtt_keepalive: int
    pu_mqtt_max_client_connection_rate: str
    pu_mqtt_max_client_id_len: int
    pu_mqtt_max_clients: int
    pu_mqtt_max_len_message_queue: int
    pu_mqtt_max_payload_size: int
    pu_mqtt_max_qos: int
    pu_mqtt_max_topic_alias: int
    pu_mqtt_max_topic_levels: int
    pu_mqtt_port: int
    pu_mqtt_secure: bool

    pu_time_window_sizes: list[int]

    @classmethod
    def current(cls) -> CurrentInstanceSettingsV1:
        return cls(
            pu_available_name_entity_symbols=(
                settings.pu_available_name_entity_symbols
            ),
            pu_available_topic_symbols=settings.pu_available_topic_symbols,
            pu_datapipe_limit_unit_node_per_one_panel=(
                runtime.get().pu_datapipe_limit_unit_node_per_one_panel
            ),
            pu_instance_cipher_max_length=(
                runtime.get().pu_instance_cipher_max_length
            ),
            pu_instance_http_connect_timeout=(
                runtime.get().pu_instance_http_connect_timeout
            ),
            pu_instance_http_timeout=runtime.get().pu_instance_http_timeout,
            pu_instance_max_pagination_size=(
                runtime.get().pu_instance_max_pagination_size
            ),
            pu_instance_max_state_size=runtime.get().pu_instance_max_state_size,
            pu_instance_registry_max_size=(
                runtime.get().pu_instance_registry_max_size
            ),
            pu_instance_registry_min_interval_sync=(
                runtime.get().pu_instance_registry_min_interval_sync
            ),
            pu_instance_retention_days=runtime.get().pu_instance_retention_days,
            pu_instance_unit_log_expiration=(
                runtime.get().pu_instance_unit_log_expiration
            ),
            pu_instance_unit_state_send_interval=(
                runtime.get().pu_instance_unit_state_send_interval
            ),
            pu_instance_user_auth_token_expiration=(
                runtime.get().pu_instance_user_auth_token_expiration
            ),
            pu_mqtt_client_max_bytes_rate=(
                runtime.get().pu_mqtt_client_max_bytes_rate
            ),
            pu_mqtt_client_max_messages_rate=(
                runtime.get().pu_mqtt_client_max_messages_rate
            ),
            pu_mqtt_host=settings.pu_mqtt_host,
            pu_mqtt_keepalive=runtime.get().pu_mqtt_keepalive,
            pu_mqtt_max_client_connection_rate=(
                runtime.get().pu_mqtt_max_client_connection_rate
            ),
            pu_mqtt_max_client_id_len=runtime.get().pu_mqtt_max_client_id_len,
            pu_mqtt_max_clients=runtime.get().pu_mqtt_max_clients,
            pu_mqtt_max_len_message_queue=(
                runtime.get().pu_mqtt_max_len_message_queue
            ),
            pu_mqtt_max_payload_size=runtime.get().pu_mqtt_max_payload_size,
            pu_mqtt_max_qos=runtime.get().pu_mqtt_max_qos,
            pu_mqtt_max_topic_alias=runtime.get().pu_mqtt_max_topic_alias,
            pu_mqtt_max_topic_levels=runtime.get().pu_mqtt_max_topic_levels,
            pu_mqtt_port=settings.pu_mqtt_port,
            pu_mqtt_secure=settings.pu_mqtt_secure,
            pu_time_window_sizes=list(settings.pu_time_window_sizes),
        )


class CurrentInstanceStateV1(BaseModel):
    instance_datetime: datetime
    last_successful_start_datetime: datetime | None = None
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
    email: str
    telegram: str

    @classmethod
    def current(cls) -> CurrentInstanceContactsV1:
        return cls(
            email=runtime.get().pu_instance_owner_email,
            telegram=runtime.get().pu_instance_owner_tg,
        )


class CurrentInstanceSchemaV1(BaseModel):
    schema_version: Literal["v1"] = "v1"
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    swagger: str = f"{settings.pu_link_prefix}/docs"
    grafana: str = f"{settings.pu_link}/grafana/"
    telegram_bot: str = Field(
        default_factory=lambda: runtime.get().pu_telegram_bot_link
    )
    feature_flags: FeatureFlags = Field(default_factory=FeatureFlags.current)
    settings: CurrentInstanceSettingsV1 = Field(
        default_factory=CurrentInstanceSettingsV1.current
    )
    state: CurrentInstanceStateV1
    metrics: CurrentInstanceMetricsV1
    contacts: CurrentInstanceContactsV1 = Field(
        default_factory=CurrentInstanceContactsV1.current
    )
    icon_uuid: uuid_pkg.UUID = Field(
        default_factory=lambda: runtime.get().icon_uuid
    )
    latitude: float | None = Field(
        default_factory=lambda: runtime.get().pu_instance_lat
    )
    longitude: float | None = Field(
        default_factory=lambda: runtime.get().pu_instance_lon
    )
