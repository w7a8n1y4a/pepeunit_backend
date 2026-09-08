import base64
import enum
import json
import re
import string
from typing import ClassVar, Literal
from urllib.parse import urlparse

import httpx
import toml
from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

with open("pyproject.toml") as f:
    data = toml.loads(f.read())


class SettingsValidationMixin:
    @staticmethod
    def require_non_empty(value: str, field_name: str) -> str:
        if not value.strip():
            msg = f"{field_name} must not be empty"
            raise ValueError(msg)
        return value

    @classmethod
    def require_host(cls, value: str, field_name: str) -> str:
        value = cls.require_non_empty(value, field_name)
        if "://" in value or "/" in value or " " in value:
            msg = f"{field_name} must be a hostname without a URL scheme"
            raise ValueError(msg)
        return value

    @staticmethod
    def require_path_prefix(value: str, field_name: str) -> str:
        if not value.startswith("/"):
            msg = f"{field_name} must start with '/'"
            raise ValueError(msg)
        if value != "/" and value.endswith("/"):
            msg = f"{field_name} must not end with '/'"
            raise ValueError(msg)
        return value

    @classmethod
    def require_url(
        cls,
        value: str,
        schemes: tuple[str, ...],
        field_name: str,
    ) -> str:
        value = cls.require_non_empty(value, field_name)
        parsed = urlparse(value)
        if parsed.scheme not in schemes:
            allowed = ", ".join(schemes)
            msg = f"{field_name} must use one of schemes: {allowed}"
            raise ValueError(msg)
        if not parsed.hostname:
            msg = f"{field_name} must include a hostname"
            raise ValueError(msg)
        return value

    @classmethod
    def require_http_url(cls, value: str, field_name: str) -> str:
        return cls.require_url(value, ("http", "https"), field_name)

    @staticmethod
    def env_name(info: ValidationInfo) -> str:
        return info.field_name.upper()


class ClickHouseConnectionParams(SettingsValidationMixin, BaseModel):
    protocol: str = Field(max_length=128)
    host: str = Field(max_length=128)
    port: int | None = Field(default=9000, ge=1, le=65535)
    user: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=128)
    database: str = Field(default="default", max_length=128)

    @field_validator("protocol", "database")
    @classmethod
    def validate_required(cls, value: str) -> str:
        return cls.require_non_empty(value, "PU_CLICKHOUSE_DATABASE_URL")

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        return cls.require_host(value, "PU_CLICKHOUSE_DATABASE_URL")

    @classmethod
    def from_connection_string(
        cls, conn_str: str
    ) -> ClickHouseConnectionParams:
        if conn_str.startswith("clickhouse+"):
            conn_str = conn_str.split("+", 1)[1]

        parsed = urlparse(conn_str)
        if not parsed.hostname:
            msg = "PU_CLICKHOUSE_DATABASE_URL must include a hostname"
            raise ValueError(msg)

        return cls(
            protocol=parsed.scheme,
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/") or "default",
        )


class FeatureFlagSettings(BaseModel):
    pu_ff_telegram_bot_enable: bool = True
    pu_ff_grafana_integration_enable: bool = True
    pu_ff_datapipe_enable: bool = True
    pu_ff_datapipe_default_last_value_enable: bool = True
    pu_ff_prometheus_enable: bool = True
    pu_ff_federation_enable: bool = True


class ProjectSettings(BaseModel):
    project_name: str = data["project"]["name"]
    version: str = data["project"]["version"]
    description: str = data["project"]["description"]
    authors: list = data["project"]["authors"]
    license: str = data["project"]["license"]["text"]


class LogFormat(str, enum.Enum):
    JSON = "json"
    PLAIN = "plain"


class BackendLogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LoggingSettings(BaseModel):
    pu_log_format: LogFormat = LogFormat.JSON.value
    pu_min_log_level: BackendLogLevel = BackendLogLevel.INFO.value

    @field_validator("pu_log_format", mode="before")
    @classmethod
    def normalize_log_format(cls, value: str) -> str:
        return str(value).lower()

    @field_validator("pu_min_log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return str(value).upper()


class AppSettings(SettingsValidationMixin, BaseModel):
    _EMAIL_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    _DEFAULT_TIME_WINDOW_SIZES: ClassVar[list[int]] = [
        60,
        300,
        600,
        900,
        1200,
        1800,
        3600,
        7200,
        10800,
        14400,
        21600,
        28800,
        43200,
        86400,
    ]

    pu_app_prefix: str = Field(default="/pepeunit", max_length=128)
    pu_api_v1_prefix: str = Field(default="/api/v1", max_length=128)

    pu_worker_count: int = Field(default=2, ge=2, le=128)

    pu_domain: str = Field(max_length=128)
    pu_secure: bool = True

    pu_auth_token_expiration: int = Field(
        default=2_678_400, ge=600, le=11_059_200
    )
    pu_save_repo_path: str = Field(default="repo_cache", max_length=128)
    pu_prometheus_multiproc_dir: str = Field(
        default="./prometheus_metrics", max_length=128
    )

    pu_min_interval_sync_repository: int = Field(default=10, ge=1, le=1800)

    pu_state_send_interval: int = Field(default=60, ge=1, le=600)
    pu_max_external_repo_size: int = Field(default=50, ge=0, le=1024)
    pu_max_cipher_length: int = Field(default=1_000_000, ge=0, le=1_000_000)
    pu_http_timeout: float = Field(default=30.0, ge=0, le=120)
    pu_http_connect_timeout: float = Field(default=15.0, ge=0, le=60)
    pu_instance_max_state_size: int = Field(default=4096, ge=4096, le=65536)
    pu_instance_retention_days: int = Field(default=60, ge=1, le=120)

    pu_admin_email: str = Field(default="", max_length=128)
    pu_admin_tg: str = Field(default="", max_length=128)

    pu_unit_log_expiration: int = Field(default=86_400, ge=60, le=604_800)

    pu_max_pagination_size: int = Field(default=100, ge=1, le=500)

    pu_available_topic_symbols: str = Field(
        default=string.ascii_letters + string.digits + "/_-",
        max_length=128,
    )
    pu_available_name_entity_symbols: str = Field(
        default=string.ascii_letters + string.digits + "_-.",
        max_length=128,
    )
    pu_available_password_symbols: str = Field(
        default=string.ascii_letters + string.digits + string.punctuation,
        max_length=128,
    )

    pu_http_type: str = "https"
    pu_link: str = ""
    pu_link_prefix: str = ""
    pu_link_prefix_and_v1: str = ""
    pu_time_window_sizes: list[int] | None = None

    @field_validator("pu_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return cls.require_host(value, "PU_DOMAIN")

    @field_validator("pu_app_prefix", "pu_api_v1_prefix")
    @classmethod
    def validate_path_prefix(cls, value: str, info: ValidationInfo) -> str:
        return cls.require_path_prefix(value, cls.env_name(info))

    @field_validator("pu_admin_email")
    @classmethod
    def validate_admin_email(cls, value: str) -> str:
        if value and not cls._EMAIL_RE.fullmatch(value):
            msg = "PU_ADMIN_EMAIL must be a valid email or empty"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def compute_app_links(self):
        self.pu_http_type = "https" if self.pu_secure else "http"
        self.pu_link = f"{self.pu_http_type}://{self.pu_domain}"
        self.pu_link_prefix = self.pu_link + self.pu_app_prefix
        self.pu_link_prefix_and_v1 = (
            self.pu_link_prefix + self.pu_api_v1_prefix
        )
        self.pu_time_window_sizes = list(self._DEFAULT_TIME_WINDOW_SIZES)
        return self

    def http_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            self.pu_http_timeout,
            connect=self.pu_http_connect_timeout,
        )

    def git_http_env(self) -> dict[str, str]:
        return {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_HTTP_LOW_SPEED_LIMIT": "1000",
            "GIT_HTTP_LOW_SPEED_TIME": str(int(self.pu_http_timeout)),
        }


class SecuritySettings(SettingsValidationMixin, BaseModel):
    _AES_KEY_SIZES: ClassVar[set[int]] = {16, 24, 32}

    pu_secret_key: str = Field(max_length=128)
    pu_encrypt_key: str = Field(max_length=128)
    pu_static_salt: str = Field(max_length=128)

    @field_validator("pu_secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        value = cls.require_non_empty(value, "PU_SECRET_KEY")
        if len(value) < 16:
            msg = "PU_SECRET_KEY must be at least 16 characters"
            raise ValueError(msg)
        return value

    @field_validator("pu_encrypt_key")
    @classmethod
    def validate_encrypt_key(cls, value: str) -> str:
        value = cls.require_non_empty(value, "PU_ENCRYPT_KEY")
        try:
            decoded = base64.b64decode(value.encode())
        except Exception as exc:
            msg = "PU_ENCRYPT_KEY must be a valid base64 string"
            raise ValueError(msg) from exc
        if len(decoded) not in cls._AES_KEY_SIZES:
            msg = "PU_ENCRYPT_KEY must decode to 16, 24 or 32 bytes"
            raise ValueError(msg)
        return value

    @field_validator("pu_static_salt")
    @classmethod
    def validate_static_salt(cls, value: str) -> str:
        return cls.require_non_empty(value, "PU_STATIC_SALT")


class DatabaseSettings(SettingsValidationMixin, BaseModel):
    pu_sqlalchemy_database_url: str = Field(max_length=1024)
    pu_clickhouse_database_url: str = Field(max_length=1024)
    pu_redis_url: str = Field(default="redis://redis:6379/0", max_length=1024)
    pu_clickhouse_connection: ClickHouseConnectionParams | None = None

    @field_validator("pu_sqlalchemy_database_url")
    @classmethod
    def validate_postgres_url(cls, value: str) -> str:
        return cls.require_url(
            value,
            ("postgresql", "postgresql+psycopg2", "postgresql+asyncpg"),
            "PU_SQLALCHEMY_DATABASE_URL",
        )

    @field_validator("pu_clickhouse_database_url")
    @classmethod
    def validate_clickhouse_url(cls, value: str) -> str:
        value = cls.require_non_empty(value, "PU_CLICKHOUSE_DATABASE_URL")
        ClickHouseConnectionParams.from_connection_string(value)
        return value

    @field_validator("pu_redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        return cls.require_url(value, ("redis", "rediss"), "PU_REDIS_URL")

    @model_validator(mode="after")
    def compute_clickhouse_connection(self):
        self.pu_clickhouse_connection = (
            ClickHouseConnectionParams.from_connection_string(
                self.pu_clickhouse_database_url
            )
        )
        return self


class TelegramSettings(SettingsValidationMixin, BaseModel):
    _TELEGRAM_TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^\d+:[A-Za-z0-9_-]+$"
    )

    pu_telegram_bot_mode: Literal["webhook", "pooling"] = "webhook"
    pu_telegram_del_old_webhook: bool = True
    pu_telegram_token: str = Field(default="", max_length=128)
    pu_telegram_bot_link: str = Field(default="", max_length=512)
    pu_telegram_items_per_page: int = Field(default=7, ge=1, le=20)
    pu_telegram_header_entity_length: int = Field(default=15, ge=1, le=64)
    pu_telegram_git_hash_length: int = Field(default=8, ge=1, le=16)
    pu_telegram_proxy_url: str = Field(default="", max_length=512)

    @model_validator(mode="after")
    def validate_telegram(self):
        if self.pu_ff_telegram_bot_enable:
            self.require_non_empty(self.pu_telegram_token, "PU_TELEGRAM_TOKEN")
            if not self._TELEGRAM_TOKEN_RE.fullmatch(self.pu_telegram_token):
                msg = "PU_TELEGRAM_TOKEN must look like '123456:ABC-def'"
                raise ValueError(msg)
            self.require_http_url(
                self.pu_telegram_bot_link,
                "PU_TELEGRAM_BOT_LINK",
            )
            if self.pu_telegram_proxy_url:
                self.require_url(
                    self.pu_telegram_proxy_url,
                    ("http", "https", "socks5", "socks5h"),
                    "PU_TELEGRAM_PROXY_URL",
                )

        self.pu_telegram_items_per_page = min(
            self.pu_telegram_items_per_page,
            self.pu_max_pagination_size,
        )
        return self


class MqttSettings(SettingsValidationMixin, BaseModel):
    _COUNT_RATE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[1-9]\d*(/[smh])?$"
    )
    _BYTES_RATE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^[1-9]\d*(?:\.\d+)?(?:KB|MB|GB|B)/[smh]$",
        re.IGNORECASE,
    )

    pu_mqtt_host: str = Field(max_length=128)
    pu_mqtt_secure: bool = True
    pu_mqtt_port: int = Field(default=1883, ge=1, le=65535)
    pu_mqtt_api_port: int = Field(default=18083, ge=1, le=65535)
    pu_mqtt_keepalive: int = Field(default=60, ge=0, le=600)

    pu_mqtt_username: str = Field(max_length=128)
    pu_mqtt_password: str = Field(max_length=128)

    pu_mqtt_redis_auth_url: str = Field(
        default="redis://redis:6379/0", max_length=512
    )

    pu_mqtt_max_clients: int = Field(default=1024, ge=1, le=1024)
    pu_mqtt_max_client_connection_rate: str = Field(
        default="20/s", max_length=64
    )
    pu_mqtt_max_client_id_len: int = Field(default=512, ge=1, le=1024)

    pu_mqtt_client_max_messages_rate: str = Field(
        default="30/s", max_length=64
    )
    pu_mqtt_client_max_bytes_rate: str = Field(default="1MB/s", max_length=64)

    pu_mqtt_max_payload_size: int = Field(default=256, ge=1, le=4096)
    pu_mqtt_max_qos: int = Field(default=2, ge=0, le=2)
    pu_mqtt_max_topic_levels: int = Field(default=5, ge=5, le=32)
    pu_mqtt_max_len_message_queue: int = Field(default=128, ge=1, le=1024)
    pu_mqtt_max_topic_alias: int = Field(default=128, ge=0, le=256)

    pu_mqtt_http_type: str = "https"

    @field_validator("pu_mqtt_host")
    @classmethod
    def validate_mqtt_host(cls, value: str) -> str:
        return cls.require_host(value, "PU_MQTT_HOST")

    @field_validator("pu_mqtt_username", "pu_mqtt_password")
    @classmethod
    def validate_mqtt_secret(cls, value: str, info: ValidationInfo) -> str:
        return cls.require_non_empty(value, cls.env_name(info))

    @field_validator("pu_mqtt_redis_auth_url")
    @classmethod
    def validate_mqtt_redis_url(cls, value: str) -> str:
        return cls.require_url(
            value,
            ("redis", "rediss"),
            "PU_MQTT_REDIS_AUTH_URL",
        )

    @field_validator(
        "pu_mqtt_max_client_connection_rate",
        "pu_mqtt_client_max_messages_rate",
    )
    @classmethod
    def validate_count_rate(cls, value: str, info: ValidationInfo) -> str:
        if not cls._COUNT_RATE_RE.fullmatch(value):
            msg = f"{cls.env_name(info)} must look like '20/s' or '20/m'"
            raise ValueError(msg)
        return value

    @field_validator("pu_mqtt_client_max_bytes_rate")
    @classmethod
    def validate_bytes_rate(cls, value: str) -> str:
        if not cls._BYTES_RATE_RE.fullmatch(value):
            msg = "PU_MQTT_CLIENT_MAX_BYTES_RATE must look like '1MB/s'"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def compute_mqtt_http_type(self):
        self.pu_mqtt_http_type = "https" if self.pu_mqtt_secure else "http"
        return self


class GrafanaSettings(SettingsValidationMixin, BaseModel):
    pu_grafana_admin_user: str = Field(default="", max_length=128)
    pu_grafana_admin_password: str = Field(default="", max_length=128)
    pu_grafana_limit_unit_node_per_one_panel: int = Field(
        default=10, ge=1, le=32
    )

    @model_validator(mode="after")
    def validate_grafana(self):
        if self.pu_ff_grafana_integration_enable:
            self.require_non_empty(
                self.pu_grafana_admin_user,
                "PU_GRAFANA_ADMIN_USER",
            )
            self.require_non_empty(
                self.pu_grafana_admin_password,
                "PU_GRAFANA_ADMIN_PASSWORD",
            )
        return self


class GithubSettings(BaseModel):
    pu_github_token_name: str = Field(default="", max_length=128)
    pu_github_token_pat: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def validate_github_tokens(self):
        if bool(self.pu_github_token_name) != bool(self.pu_github_token_pat):
            msg = (
                "PU_GITHUB_TOKEN_NAME and PU_GITHUB_TOKEN_PAT "
                "must be set together"
            )
            raise ValueError(msg)
        return self


class IntegrationTestSettings(SettingsValidationMixin, BaseModel):
    pu_test_integration_clear_data: bool = True
    pu_test_integration_github_public_repo_url: str = Field(
        default="https://github.com/w7a8n1y4a/github_unit_pub_test.git",
        max_length=512,
    )
    pu_test_integration_gitlab_public_repo_url: str = Field(
        default="https://git.pepemoss.com/pepe/pepeunit/units/gitlab_unit_pub_test.git",
        max_length=512,
    )
    pu_test_integration_universal_repo_url: str = Field(
        default="https://git.pepemoss.com/pepe/pepeunit/units/universal_test_unit.git",
        max_length=512,
    )
    pu_test_integration_private_repo_enable: bool = False
    pu_test_integration_private_repo_json: str = Field(
        default="", max_length=8192
    )

    @field_validator(
        "pu_test_integration_github_public_repo_url",
        "pu_test_integration_gitlab_public_repo_url",
        "pu_test_integration_universal_repo_url",
    )
    @classmethod
    def validate_repo_url(cls, value: str, info: ValidationInfo) -> str:
        return cls.require_http_url(value, cls.env_name(info))

    @model_validator(mode="after")
    def validate_private_repo_json(self):
        if self.pu_test_integration_private_repo_enable:
            raw = self.pu_test_integration_private_repo_json.strip()
            if not raw:
                msg = (
                    "PU_TEST_INTEGRATION_PRIVATE_REPO_JSON is required "
                    "when PU_TEST_INTEGRATION_PRIVATE_REPO_ENABLE=True"
                )
                raise ValueError(msg)
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                msg = (
                    "PU_TEST_INTEGRATION_PRIVATE_REPO_JSON must be valid JSON"
                )
                raise ValueError(msg) from exc
        return self


class LoadTestSettings(BaseModel):
    pu_test_load_mqtt_duration: int = Field(default=120, ge=1, le=3600)
    pu_test_load_mqtt_unit_count: int = Field(default=100, ge=1, le=1024)
    pu_test_load_mqtt_rps: int = Field(default=200, ge=1, le=1024)
    pu_test_load_mqtt_value_type: Literal["Text", "Number"] = "Text"
    pu_test_load_mqtt_duplicate_count: int = Field(default=10, ge=1, le=32)
    pu_test_load_mqtt_message_size: int = Field(default=15, ge=1, le=512)
    pu_test_load_mqtt_policy_type: Literal[
        "LastValue",
        "NRecords",
        "TimeWindow",
        "Aggregation",
    ] = "TimeWindow"
    pu_test_load_mqtt_workers: int = Field(default=10, ge=1, le=128)

    locust_headless: bool = True
    locust_users: int = Field(default=400, ge=1, le=8192)
    locust_run_time: int = Field(default=120, ge=1, le=3600)
    locust_spawn_rate: int = Field(default=10, ge=1, le=8192)


class Settings(
    BaseSettings,
    ProjectSettings,
    FeatureFlagSettings,
    LoggingSettings,
    AppSettings,
    SecuritySettings,
    DatabaseSettings,
    TelegramSettings,
    MqttSettings,
    GrafanaSettings,
    GithubSettings,
    IntegrationTestSettings,
    LoadTestSettings,
):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    @classmethod
    def load(cls) -> Settings:
        try:
            return cls()
        except ValidationError as exc:
            details = "\n".join(
                f"  - {cls._format_error_location(error)}: {error['msg']}"
                for error in exc.errors()
            )
            msg = (
                "Backend cannot start: invalid environment variables\n"
                f"{details}"
            )
            raise SystemExit(msg) from exc

    @staticmethod
    def _format_error_location(error: dict) -> str:
        return ".".join(str(part).upper() for part in error["loc"])
