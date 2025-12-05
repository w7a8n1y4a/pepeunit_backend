import logging
from logging.config import dictConfig
from typing import Final

from pythonjsonlogger import jsonlogger

from app import settings


class PepeunitJsonFormatter(jsonlogger.JsonFormatter):
    FIELD_MAPPING = {
        "asctime": "time",
        "levelname": "level",
        "name": "logger",
        "funcName": "func",
        "message": "message",
        "pathname": "file",
        "lineno": "line",
    }

    FIELD_ORDER = [
        "time",
        "level",
        "logger",
        "func",
        "message",
        "file",
        "line",
    ]

    def add_fields(self, log_record, record, message_dict) -> None:
        super().add_fields(log_record, record, message_dict)

        for old_key, new_key in self.FIELD_MAPPING.items():
            if old_key in log_record and new_key not in log_record:
                log_record[new_key] = log_record.pop(old_key)

        ordered = {}
        for key in self.FIELD_ORDER:
            if key in log_record:
                ordered[key] = log_record[key]

        for key, value in log_record.items():
            if key not in ordered:
                ordered[key] = value

        log_record.clear()
        log_record.update(ordered)


def _build_formatters() -> dict:
    if settings.pu_log_format == "plain":
        plain_format = "%(levelname)s - %(asctime)s - %(name)s - %(funcName)s - %(message)s"
        return {
            "plain": {
                "format": plain_format,
            }
        }

    json_format = (
        "%(asctime)s %(levelname)s %(name)s %(message)s "
        "%(pathname)s %(lineno)d %(funcName)s"
    )

    return {
        "json": {
            "class": "app.configs.logging_config.PepeunitJsonFormatter",
            "format": json_format,
        },
    }


def _get_default_formatter_name() -> str:
    return "plain" if settings.pu_log_format == "plain" else "json"


def _build_logging_config() -> dict:
    raw_level = settings.pu_min_log_level.upper()
    if raw_level not in {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
        "NOTSET",
    }:
        raw_level = "INFO"

    formatter_name = _get_default_formatter_name()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": _build_formatters(),
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
            },
        },
        "root": {
            "level": raw_level,
            "handlers": ["stdout"],
        },
        "loggers": {
            "gunicorn": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "gunicorn.error": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "gunicorn.access": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "uvicorn": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "alembic": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
            "httpx": {
                "level": raw_level,
                "handlers": ["stdout"],
                "propagate": False,
            },
        },
    }


LOGGING_CONFIG: Final = _build_logging_config()


def setup_logging() -> None:
    dictConfig(LOGGING_CONFIG)
    logging.getLogger(__name__)
