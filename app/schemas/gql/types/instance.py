import uuid as uuid_pkg
from datetime import datetime

import strawberry
from strawberry.scalars import JSON

from app.dto.enum import (
    GitPlatform,
    InstanceCollectionStatus,
    InstanceTrustStatus,
    IntegrationTestsStatus,
)
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class InstanceType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    url: str
    trust_status: InstanceTrustStatus
    last_ping: float | None
    last_collection_status: InstanceCollectionStatus | None
    last_success_datetime: datetime | None
    last_attempt_datetime: datetime | None
    consecutive_success_count: int
    last_collection_error: str | None
    state: JSON | None
    create_datetime: datetime


@strawberry.type()
class InstancesPageType:
    total_count: int
    instances: list[InstanceType]


@strawberry.type()
class InstanceUrlsPageType:
    total_count: int
    urls: list[str]


@strawberry.type()
class InstancePublicRegistryType:
    url: str
    platform: GitPlatform


@strawberry.type()
class InstanceRegistriesPageType:
    total_count: int
    registries: list[InstancePublicRegistryType]


@strawberry.type()
class FeatureFlagsType:
    pu_ff_telegram_bot_enable: bool
    pu_ff_grafana_integration_enable: bool
    pu_ff_datapipe_enable: bool
    pu_ff_datapipe_default_last_value_enable: bool
    pu_ff_prometheus_enable: bool
    pu_ff_federation_enable: bool


@strawberry.type()
class CurrentInstanceSettingsType:
    pu_auth_token_expiration: int
    pu_min_interval_sync_repository: int
    pu_state_send_interval: int
    pu_max_external_repo_size: int
    pu_max_cipher_length: int
    pu_http_timeout: float
    pu_http_connect_timeout: float
    pu_instance_max_state_size: int
    pu_instance_retention_days: int
    pu_unit_log_expiration: int
    pu_max_pagination_size: int
    pu_available_topic_symbols: str
    pu_available_name_entity_symbols: str
    pu_time_window_sizes: list[int]

    pu_mqtt_host: str
    pu_mqtt_secure: bool
    pu_mqtt_port: int
    pu_mqtt_keepalive: int
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

    pu_grafana_limit_unit_node_per_one_panel: int


@strawberry.type()
class CurrentInstanceStateType:
    instance_datetime: datetime
    integration_tests_datetime: datetime | None
    integration_tests_status: IntegrationTestsStatus | None
    integration_tests_success_percentage: float | None


@strawberry.type()
class CurrentInstanceMetricsType:
    user_count: int
    repository_registry_count: int
    repo_count: int
    unit_count: int
    unit_node_count: int
    unit_node_edge_count: int


@strawberry.type()
class CurrentInstanceContactsType:
    email: str
    telegram: str


@strawberry.type()
class CurrentInstanceType:
    schema_version: str
    name: str
    version: str
    description: str
    license: str
    swagger: str
    graphql: str
    grafana: str
    telegram_bot: str
    feature_flags: FeatureFlagsType
    settings: CurrentInstanceSettingsType
    state: CurrentInstanceStateType
    metrics: CurrentInstanceMetricsType
    contacts: CurrentInstanceContactsType
