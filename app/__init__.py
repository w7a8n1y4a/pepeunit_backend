from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.configs.config import Settings
from app.dto.enum import AgentType

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
    def from_connection_string(cls, conn_str: str) -> 'ClickHouseConnectionParams':
        # Удаляем префикс "clickhouse+" если он есть
        if conn_str.startswith("clickhouse+"):
            conn_str = conn_str.split("+", 1)[1]

        parsed = urlparse(conn_str)

        database = parsed.path.lstrip('/') or 'default'

        return cls(
            protocol=parsed.scheme,
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=database,
        )


settings = Settings()
settings.backend_http_type = 'https' if settings.backend_secure else 'http'
settings.mqtt_http_type = 'https' if settings.mqtt_secure else 'http'

settings.backend_link = f'{settings.backend_http_type}://{settings.backend_domain}'
settings.backend_link_prefix = settings.backend_link + settings.backend_app_prefix
settings.backend_link_prefix_and_v1 = settings.backend_link_prefix + settings.backend_api_v1_prefix

settings.clickhouse_connection = ClickHouseConnectionParams.from_connection_string(settings.clickhouse_database_url)
