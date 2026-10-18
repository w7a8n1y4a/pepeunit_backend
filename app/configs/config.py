import base64
import enum
import json
import string
from typing import ClassVar, Literal
from urllib.parse import urlparse

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

from app.configs.utc_json import UtcJson

UtcJson.install()

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


class AppSettings(SettingsValidationMixin, BaseModel):
    pu_time_window_sizes: ClassVar[list[int]] = [
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
    pu_available_topic_symbols: ClassVar[str] = (
        string.ascii_letters + string.digits + "/_-"
    )
    pu_available_name_entity_symbols: ClassVar[str] = (
        string.ascii_letters + string.digits + "_-."
    )

    pu_app_prefix: str = Field(default="/pepeunit", max_length=128)
    pu_api_v1_prefix: str = Field(default="/api/v1", max_length=128)

    pu_worker_count: int = Field(default=2, ge=2, le=128)

    pu_domain: str = Field(max_length=128)
    pu_secure: bool = True

    pu_save_repo_path: str = Field(default="repo_cache", max_length=128)
    pu_prometheus_multiproc_dir: str = Field(
        default="./prometheus_metrics", max_length=128
    )

    pu_http_type: str = "https"
    pu_link: str = ""
    pu_link_prefix: str = ""
    pu_link_prefix_and_v1: str = ""

    @field_validator("pu_domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return cls.require_host(value, "PU_DOMAIN")

    @field_validator("pu_app_prefix", "pu_api_v1_prefix")
    @classmethod
    def validate_path_prefix(cls, value: str, info: ValidationInfo) -> str:
        return cls.require_path_prefix(value, cls.env_name(info))

    @model_validator(mode="after")
    def compute_app_links(self):
        self.pu_http_type = "https" if self.pu_secure else "http"
        self.pu_link = f"{self.pu_http_type}://{self.pu_domain}"
        self.pu_link_prefix = self.pu_link + self.pu_app_prefix
        self.pu_link_prefix_and_v1 = (
            self.pu_link_prefix + self.pu_api_v1_prefix
        )
        return self


class SecuritySettings(SettingsValidationMixin, BaseModel):
    _AES_KEY_SIZES: ClassVar[set[int]] = {16, 24, 32}

    pu_secret_key: str = Field(max_length=128)
    pu_encrypt_key: str = Field(max_length=128)

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


class NotificationSettings(SettingsValidationMixin, BaseModel):
    """Notification delivery and Loki, the source of instance alerts"""

    pu_notification_loki_url: str = Field(
        default="http://loki:3100", max_length=512
    )

    @field_validator("pu_notification_loki_url")
    @classmethod
    def validate_loki_url(cls, value: str) -> str:
        return cls.require_http_url(value, "PU_NOTIFICATION_LOKI_URL")


class MqttSettings(SettingsValidationMixin, BaseModel):
    pu_mqtt_host: str = Field(max_length=128)
    pu_mqtt_secure: bool = True
    pu_mqtt_port: int = Field(default=1883, ge=1, le=65535)
    pu_mqtt_api_port: int = Field(default=18083, ge=1, le=65535)

    pu_mqtt_username: str = Field(max_length=128)
    pu_mqtt_password: str = Field(max_length=128)

    pu_mqtt_redis_auth_url: str = Field(
        default="redis://redis:6379/0", max_length=512
    )

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

    @model_validator(mode="after")
    def compute_mqtt_http_type(self):
        self.pu_mqtt_http_type = "https" if self.pu_mqtt_secure else "http"
        return self


class GrafanaSettings(BaseModel):
    pu_grafana_admin_user: str = Field(default="", max_length=128)
    pu_grafana_admin_password: str = Field(default="", max_length=128)


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
    # Empty keeps a random chat id for the data pipe recipient
    pu_test_integration_telegram_chat_id: str = Field(
        default="", max_length=32
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
    AppSettings,
    SecuritySettings,
    DatabaseSettings,
    NotificationSettings,
    MqttSettings,
    GrafanaSettings,
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
