import enum
import re
import uuid as uuid_pkg
from typing import ClassVar, Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.configs.config import (
    BackendLogLevel,
    LogFormat,
    SettingsValidationMixin,
)
from app.configs.error_codes import ErrorCode


class InstanceSettingsData(SettingsValidationMixin, BaseModel):
    """Stored instance settings. Ranges match the old env settings."""

    _EMAIL_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    _TELEGRAM_TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^\d+:[A-Za-z0-9_-]+$"
    )
    _COUNT_RATE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[1-9]\d*(/[smh])?$"
    )
    _BYTES_RATE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[1-9]\d*(?:\.\d+)?(?:KB|MB|GB|B)/[smh]$",
        re.IGNORECASE,
    )

    icon_uuid: uuid_pkg.UUID

    pu_datapipe_buffer_flush_interval: int = Field(ge=1, le=3600)
    pu_datapipe_buffer_max_size: int = Field(ge=1, le=1_000_000)
    pu_datapipe_config_sync_interval: int = Field(ge=1, le=86_400)
    pu_datapipe_default_last_value_enable: bool
    pu_datapipe_limit_unit_io_per_one_panel: int = Field(ge=1, le=32)
    pu_datapipe_mqtt_keepalive: int = Field(ge=1, le=600)
    pu_datapipe_nrecords_cleanup_interval: int = Field(ge=1, le=604_800)

    pu_ff_datapipe_enable: bool
    pu_ff_federation_enable: bool
    pu_ff_grafana_integration_enable: bool
    pu_ff_notification_enable: bool
    pu_ff_prometheus_enable: bool
    pu_ff_telegram_bot_enable: bool

    pu_instance_cipher_max_length: int = Field(ge=100_000, le=5_000_000)
    pu_instance_github_token_name: str = Field(max_length=128)
    pu_instance_github_token_pat: str = Field(max_length=128)
    pu_instance_http_connect_timeout: float = Field(ge=1, le=60)
    pu_instance_http_timeout: float = Field(ge=1, le=120)
    pu_instance_lat: float | None = Field(default=None, ge=-90, le=90)
    pu_instance_log_format: LogFormat
    pu_instance_log_min_level: BackendLogLevel
    pu_instance_lon: float | None = Field(default=None, ge=-180, le=180)
    pu_instance_max_pagination_size: int = Field(ge=1, le=500)
    pu_instance_max_state_size: int = Field(ge=4096, le=65536)
    pu_instance_owner_email: str = Field(max_length=128)
    pu_instance_owner_tg: str = Field(max_length=128)
    pu_instance_repo_max_size: int = Field(ge=1, le=1024)
    pu_instance_repo_min_interval_sync: int = Field(ge=1, le=1800)
    pu_instance_retention_days: int = Field(ge=1, le=120)
    pu_instance_unit_log_expiration: int = Field(ge=60, le=604_800)
    pu_instance_unit_state_send_interval: int = Field(ge=1, le=600)
    pu_instance_user_auth_token_expiration: int = Field(ge=600, le=11_059_200)
    pu_instance_user_max_count: int = Field(ge=1, le=1_000_000)
    pu_instance_user_max_group: int = Field(ge=8, le=32)

    pu_mqtt_client_max_bytes_rate: str = Field(max_length=64)
    pu_mqtt_client_max_messages_rate: str = Field(max_length=64)
    pu_mqtt_keepalive: int = Field(ge=1, le=600)
    pu_mqtt_max_client_connection_rate: str = Field(max_length=64)
    pu_mqtt_max_client_id_len: int = Field(ge=1, le=1024)
    pu_mqtt_max_clients: int = Field(ge=1, le=1024)
    pu_mqtt_max_len_message_queue: int = Field(ge=1, le=1024)
    pu_mqtt_max_payload_size: int = Field(ge=1, le=4096)
    pu_mqtt_max_qos: int = Field(ge=0, le=2)
    pu_mqtt_max_topic_alias: int = Field(ge=0, le=256)
    pu_mqtt_max_topic_levels: int = Field(ge=5, le=32)

    pu_notification_data_pipe_alert_batch: int = Field(ge=1, le=1_000)
    pu_notification_small_text_limit: int = Field(ge=1, le=96)
    pu_notification_stream_maxlen: int = Field(ge=1, le=10_000)
    pu_notification_telegram_alert_text_limit: int = Field(ge=1, le=4096)
    pu_notification_telegram_instance_rate: int = Field(ge=1, le=30)
    pu_notification_telegram_user_interval_seconds: float = Field(ge=1, le=60)

    pu_telegram_bot_link: str = Field(max_length=512)
    pu_telegram_bot_mode: Literal["webhook", "pooling"]
    pu_telegram_git_hash_length: int = Field(ge=1, le=16)
    pu_telegram_header_entity_length: int = Field(ge=1, le=64)
    pu_telegram_items_per_page: int = Field(ge=1, le=20)
    pu_telegram_proxy_url: str = Field(max_length=512)
    pu_telegram_token: str = Field(max_length=128)

    @staticmethod
    def _enum_text(value) -> str:
        # str(StrEnum) is "Class.NAME" on Python 3.14, the stored text is .value.
        if isinstance(value, enum.Enum):
            return str(value.value)
        return str(value)

    @field_validator("pu_instance_log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: str) -> str:
        return cls._enum_text(value).lower()

    @field_validator("pu_instance_log_min_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return cls._enum_text(value).upper()

    @field_validator("pu_instance_owner_email")
    @classmethod
    def validate_owner_email(cls, value: str) -> str:
        if value and not cls._EMAIL_RE.fullmatch(value):
            msg = "pu_instance_owner_email must be a valid email or empty"
            raise ErrorCode.coded(
                ErrorCode.INSTANCE_SETTINGS_EMAIL_INVALID, msg
            )
        return value

    @field_validator("pu_telegram_token")
    @classmethod
    def validate_telegram_token(cls, value: str) -> str:
        if value and not cls._TELEGRAM_TOKEN_RE.fullmatch(value):
            msg = (
                "pu_telegram_token must look like '123456:ABC-def' or be empty"
            )
            raise ErrorCode.coded(
                ErrorCode.INSTANCE_SETTINGS_TELEGRAM_TOKEN_INVALID, msg
            )
        return value

    @field_validator(
        "pu_mqtt_max_client_connection_rate",
        "pu_mqtt_client_max_messages_rate",
    )
    @classmethod
    def validate_count_rate(cls, value: str, info: ValidationInfo) -> str:
        if not cls._COUNT_RATE_RE.fullmatch(value):
            msg = f"{info.field_name} must look like '20/s' or '20/m'"
            raise ErrorCode.coded(
                ErrorCode.INSTANCE_SETTINGS_COUNT_RATE_INVALID, msg
            )
        return value

    @field_validator("pu_mqtt_client_max_bytes_rate")
    @classmethod
    def validate_bytes_rate(cls, value: str) -> str:
        if not cls._BYTES_RATE_RE.fullmatch(value):
            msg = "pu_mqtt_client_max_bytes_rate must look like '1MB/s'"
            raise ErrorCode.coded(
                ErrorCode.INSTANCE_SETTINGS_BYTES_RATE_INVALID, msg
            )
        return value

    @model_validator(mode="after")
    def validate_linked_fields(self):
        if self.pu_ff_grafana_integration_enable:
            from app import settings

            if not (
                settings.pu_grafana_admin_user
                and settings.pu_grafana_admin_password
            ):
                msg = (
                    "Grafana admin credentials are empty, "
                    "pu_ff_grafana_integration_enable stays off"
                )
                raise ErrorCode.coded(
                    ErrorCode.INSTANCE_SETTINGS_GRAFANA_CREDENTIALS, msg
                )

        if self.pu_ff_telegram_bot_enable:
            self.require_http_url(
                self.pu_telegram_bot_link, "pu_telegram_bot_link"
            )
            if self.pu_telegram_proxy_url:
                self.require_url(
                    self.pu_telegram_proxy_url,
                    ("http", "https", "socks5", "socks5h"),
                    "pu_telegram_proxy_url",
                )

        self.pu_telegram_items_per_page = min(
            self.pu_telegram_items_per_page,
            self.pu_instance_max_pagination_size,
        )

        if bool(self.pu_instance_github_token_name) != bool(
            self.pu_instance_github_token_pat
        ):
            msg = (
                "pu_instance_github_token_name and "
                "pu_instance_github_token_pat must be set together"
            )
            raise ErrorCode.coded(
                ErrorCode.INSTANCE_SETTINGS_GITHUB_TOKEN_PAIR, msg
            )
        return self


class InstanceSettingsRead(InstanceSettingsData):
    """Owner view of the stored row."""


class InstanceSettingsUpdate(BaseModel):
    """Partial owner update. Omitted fields stay as they are."""

    pu_datapipe_buffer_flush_interval: int | None = None
    pu_datapipe_buffer_max_size: int | None = None
    pu_datapipe_config_sync_interval: int | None = None
    pu_datapipe_default_last_value_enable: bool | None = None
    pu_datapipe_limit_unit_io_per_one_panel: int | None = None
    pu_datapipe_mqtt_keepalive: int | None = None
    pu_datapipe_nrecords_cleanup_interval: int | None = None

    pu_ff_datapipe_enable: bool | None = None
    pu_ff_federation_enable: bool | None = None
    pu_ff_grafana_integration_enable: bool | None = None
    pu_ff_notification_enable: bool | None = None
    pu_ff_prometheus_enable: bool | None = None
    pu_ff_telegram_bot_enable: bool | None = None

    pu_instance_cipher_max_length: int | None = None
    pu_instance_github_token_name: str | None = None
    pu_instance_github_token_pat: str | None = None
    pu_instance_http_connect_timeout: float | None = None
    pu_instance_http_timeout: float | None = None
    pu_instance_lat: float | None = None
    pu_instance_log_format: LogFormat | None = None
    pu_instance_log_min_level: BackendLogLevel | None = None
    pu_instance_lon: float | None = None
    pu_instance_max_pagination_size: int | None = None
    pu_instance_max_state_size: int | None = None
    pu_instance_owner_email: str | None = None
    pu_instance_owner_tg: str | None = None
    pu_instance_repo_max_size: int | None = None
    pu_instance_repo_min_interval_sync: int | None = None
    pu_instance_retention_days: int | None = None
    pu_instance_unit_log_expiration: int | None = None
    pu_instance_unit_state_send_interval: int | None = None
    pu_instance_user_auth_token_expiration: int | None = None
    pu_instance_user_max_count: int | None = None
    pu_instance_user_max_group: int | None = None

    pu_mqtt_client_max_bytes_rate: str | None = None
    pu_mqtt_client_max_messages_rate: str | None = None
    pu_mqtt_keepalive: int | None = None
    pu_mqtt_max_client_connection_rate: str | None = None
    pu_mqtt_max_client_id_len: int | None = None
    pu_mqtt_max_clients: int | None = None
    pu_mqtt_max_len_message_queue: int | None = None
    pu_mqtt_max_payload_size: int | None = None
    pu_mqtt_max_qos: int | None = None
    pu_mqtt_max_topic_alias: int | None = None
    pu_mqtt_max_topic_levels: int | None = None

    pu_notification_data_pipe_alert_batch: int | None = None
    pu_notification_small_text_limit: int | None = None
    pu_notification_stream_maxlen: int | None = None
    pu_notification_telegram_alert_text_limit: int | None = None
    pu_notification_telegram_instance_rate: int | None = None
    pu_notification_telegram_user_interval_seconds: float | None = None

    pu_telegram_bot_link: str | None = None
    pu_telegram_bot_mode: Literal["webhook", "pooling"] | None = None
    pu_telegram_git_hash_length: int | None = None
    pu_telegram_header_entity_length: int | None = None
    pu_telegram_items_per_page: int | None = None
    pu_telegram_proxy_url: str | None = None
    pu_telegram_token: str | None = None
