from dotenv import load_dotenv

from app.configs.config import (
    BackendLogLevel,
    ClickHouseConnectionParams,
    LogFormat,
    Settings,
)

load_dotenv()

settings = Settings.load()

__all__ = [
    "BackendLogLevel",
    "ClickHouseConnectionParams",
    "LogFormat",
    "settings",
]
