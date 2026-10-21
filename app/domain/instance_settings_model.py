import uuid as uuid_pkg
from typing import ClassVar

import httpx
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field, SQLModel

from app.domain.icon_model import Icon


class InstanceSettings(SQLModel, table=True):
    """Single row of instance settings that can change without a new deploy."""

    __tablename__ = "instance_settings"

    ROW_UUID: ClassVar[uuid_pkg.UUID] = uuid_pkg.UUID(
        "00000000-0000-4000-8000-000000000001"
    )

    uuid: uuid_pkg.UUID = Field(
        primary_key=True,
        nullable=False,
        default=ROW_UUID,
    )

    # Default picture is generated from the instance domain.
    icon_uuid: uuid_pkg.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey(
                Icon.__table__.c.uuid,
                name="instance_settings_icon_uuid_fkey",
                ondelete="RESTRICT",
            ),
            nullable=False,
            index=True,
        )
    )

    # Datapipe reads these from Postgres. The backend only stores them.
    pu_datapipe_buffer_flush_interval: int = Field(nullable=False, default=5)
    pu_datapipe_buffer_max_size: int = Field(nullable=False, default=1000)
    pu_datapipe_config_sync_interval: int = Field(nullable=False, default=60)
    pu_datapipe_default_last_value_enable: bool = Field(
        nullable=False, default=True
    )
    pu_datapipe_limit_unit_io_per_one_panel: int = Field(
        nullable=False, default=10
    )
    pu_datapipe_mqtt_keepalive: int = Field(nullable=False, default=60)
    pu_datapipe_nrecords_cleanup_interval: int = Field(
        nullable=False, default=3600
    )

    pu_ff_datapipe_enable: bool = Field(nullable=False, default=True)
    pu_ff_federation_enable: bool = Field(nullable=False, default=True)
    pu_ff_grafana_integration_enable: bool = Field(
        nullable=False, default=True
    )
    pu_ff_notification_enable: bool = Field(nullable=False, default=True)
    pu_ff_prometheus_enable: bool = Field(nullable=False, default=True)
    pu_ff_telegram_bot_enable: bool = Field(nullable=False, default=False)

    pu_instance_cipher_max_length: int = Field(
        nullable=False, default=1_000_000
    )
    pu_instance_github_token_name: str = Field(
        nullable=False, default="", max_length=128
    )
    pu_instance_github_token_pat: str = Field(
        nullable=False, default="", max_length=128
    )
    pu_instance_http_connect_timeout: float = Field(
        nullable=False, default=15.0
    )
    pu_instance_http_timeout: float = Field(nullable=False, default=30.0)
    pu_instance_lat: float | None = Field(default=None, nullable=True)
    pu_instance_log_format: str = Field(
        nullable=False, default="json", max_length=16
    )
    pu_instance_log_min_level: str = Field(
        nullable=False, default="INFO", max_length=16
    )
    pu_instance_lon: float | None = Field(default=None, nullable=True)
    pu_instance_max_pagination_size: int = Field(nullable=False, default=100)
    pu_instance_max_state_size: int = Field(nullable=False, default=4096)
    pu_instance_owner_email: str = Field(
        nullable=False, default="", max_length=128
    )
    pu_instance_owner_tg: str = Field(
        nullable=False, default="", max_length=128
    )
    pu_instance_repo_max_size: int = Field(nullable=False, default=50)
    pu_instance_repo_min_interval_sync: int = Field(nullable=False, default=10)
    pu_instance_retention_days: int = Field(nullable=False, default=60)
    pu_instance_unit_log_expiration: int = Field(
        nullable=False, default=86_400
    )
    # Devices still read this as PU_STATE_SEND_INTERVAL in env.
    pu_instance_unit_state_send_interval: int = Field(
        nullable=False, default=60
    )
    pu_instance_user_auth_token_expiration: int = Field(
        nullable=False, default=2_678_400
    )
    # How many user rows this instance may hold.
    pu_instance_user_max_count: int = Field(nullable=False, default=1024)
    # How many groups one account may own.
    pu_instance_user_max_group: int = Field(nullable=False, default=16)

    pu_mqtt_client_max_bytes_rate: str = Field(
        nullable=False, default="1MB/s", max_length=64
    )
    pu_mqtt_client_max_messages_rate: str = Field(
        nullable=False, default="30/s", max_length=64
    )
    pu_mqtt_keepalive: int = Field(nullable=False, default=60)
    pu_mqtt_max_client_connection_rate: str = Field(
        nullable=False, default="20/s", max_length=64
    )
    pu_mqtt_max_client_id_len: int = Field(nullable=False, default=512)
    pu_mqtt_max_clients: int = Field(nullable=False, default=1024)
    pu_mqtt_max_len_message_queue: int = Field(nullable=False, default=128)
    pu_mqtt_max_payload_size: int = Field(nullable=False, default=256)
    pu_mqtt_max_qos: int = Field(nullable=False, default=2)
    pu_mqtt_max_topic_alias: int = Field(nullable=False, default=128)
    pu_mqtt_max_topic_levels: int = Field(nullable=False, default=5)

    pu_notification_data_pipe_alert_batch: int = Field(
        nullable=False, default=100
    )
    pu_notification_small_text_limit: int = Field(nullable=False, default=48)
    pu_notification_stream_maxlen: int = Field(nullable=False, default=100)
    pu_notification_telegram_alert_text_limit: int = Field(
        nullable=False, default=4000
    )
    pu_notification_telegram_instance_rate: int = Field(
        nullable=False, default=20
    )
    pu_notification_telegram_user_interval_seconds: float = Field(
        nullable=False, default=2
    )

    pu_telegram_bot_link: str = Field(
        nullable=False, default="", max_length=512
    )
    pu_telegram_bot_mode: str = Field(
        nullable=False, default="pooling", max_length=16
    )
    pu_telegram_git_hash_length: int = Field(nullable=False, default=8)
    pu_telegram_header_entity_length: int = Field(nullable=False, default=15)
    pu_telegram_items_per_page: int = Field(nullable=False, default=7)
    pu_telegram_proxy_url: str = Field(
        nullable=False, default="", max_length=512
    )
    pu_telegram_token: str = Field(nullable=False, default="", max_length=128)

    def http_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            float(self.pu_instance_http_timeout),
            connect=float(self.pu_instance_http_connect_timeout),
        )
