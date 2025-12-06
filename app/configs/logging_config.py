import logging
import re
from logging.config import dictConfig
from typing import Final

from pythonjsonlogger import jsonlogger

from app import settings


class PepeunitJsonFormatter(jsonlogger.JsonFormatter):
    FIELD_MAPPING = {
        "asctime": "time",
        "levelname": "level",
        "name": "logger",
        "message": "message",
    }

    FIELD_ORDER = [
        "time",
        "level",
        "logger",
        "message",
        "traceback",
    ]

    def add_fields(self, log_record, record, message_dict) -> None:
        super().add_fields(log_record, record, message_dict)

        self._add_traceback(log_record, record)
        self._normalize_uvicorn_access(log_record, record)
        self._remap_and_order_fields(log_record)

    @staticmethod
    def _add_traceback(log_record, record) -> None:
        if not record.exc_info:
            return

        formatter = logging.Formatter()
        try:
            traceback_str = formatter.formatException(record.exc_info)
        except Exception:
            traceback_str = None

        if traceback_str:
            log_record["traceback"] = traceback_str

        log_record.pop("exc_info", None)

    @staticmethod
    def _normalize_uvicorn_access(log_record, record) -> None:
        if getattr(record, "name", None) != "uvicorn.access":
            return

        msg = log_record.get("message")
        if not isinstance(msg, str):
            return

        pattern = re.compile(
            r"^(?P<client_ip>[^:]+):\d+\s+-\s+"
            r'"(?P<method>[A-Z]+)\s+(?P<path>[^ ]+)\s+HTTP/(?P<http_version>[^"]+)"\s+'
            r"(?P<status_code>\d+)\s*"
        )

        m = pattern.match(msg)
        if m:
            log_record["client_ip"] = m.group("client_ip")
            log_record["http_method"] = m.group("method")
            log_record["http_path"] = m.group("path")
            log_record["http_version"] = m.group("http_version")
            log_record["http_status_code"] = int(m.group("status_code"))

            log_record["message"] = (
                f"{m.group('method')} {m.group('path')} {m.group('status_code')}"
            )
            return

        normalized = re.sub(r"^([^:]+):\d+(\s+-\s+)", r"\1\2", msg)
        log_record["message"] = normalized

    def _remap_and_order_fields(self, log_record) -> None:
        for old_key, new_key in self.FIELD_MAPPING.items():
            if old_key in log_record and new_key not in log_record:
                log_record[new_key] = log_record.pop(old_key)

        ordered: dict = {}
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
        plain_format = "%(levelname)s - %(asctime)s - %(name)s - %(message)s"
        return {
            "plain": {
                "format": plain_format,
            }
        }

    json_format = "%(asctime)s %(levelname)s %(name)s %(message)s %(funcName)s"

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
