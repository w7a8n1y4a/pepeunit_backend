from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.configs.config import Settings

load_dotenv()


@dataclass
class ClickHouseConnectionParams:
    protocol: str
    host: str
    port: int
    user: str
    password: str
    database: str

    @classmethod
    def from_connection_string(
        cls, conn_str: str
    ) -> "ClickHouseConnectionParams":
        # Удаляем префикс "clickhouse+" если он есть
        if conn_str.startswith("clickhouse+"):
            conn_str = conn_str.split("+", 1)[1]

        parsed = urlparse(conn_str)

        database = parsed.path.lstrip("/") or "default"

        return cls(
            protocol=parsed.scheme,
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=database,
        )


settings = Settings()
settings.pu_http_type = "https" if settings.pu_secure else "http"
settings.pu_mqtt_http_type = "https" if settings.pu_mqtt_secure else "http"

settings.pu_link = f"{settings.pu_http_type}://{settings.pu_domain}"
settings.pu_link_prefix = settings.pu_link + settings.pu_app_prefix
settings.pu_link_prefix_and_v1 = (
    settings.pu_link_prefix + settings.pu_api_v1_prefix
)
if settings.pu_clickhouse_database_url:
    settings.pu_clickhouse_connection = (
        ClickHouseConnectionParams.from_connection_string(
            settings.pu_clickhouse_database_url
        )
    )
settings.pu_time_window_sizes = [
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
