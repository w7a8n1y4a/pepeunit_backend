import logging
import re
from logging.config import dictConfig
from typing import Final

from pythonjsonlogger import jsonlogger

from app.configs.config import LogFormat
from app.configs.runtime import runtime


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


class UvicornAccessFilter(logging.Filter):
    """Drop the caller address. It is a container on this network, and the port changes every call."""

    _client = re.compile(r"^[^\s:]+:\d+ - ")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.access":
            return True

        try:
            msg = record.getMessage()
        except Exception:
            return True

        if not isinstance(msg, str):
            return True

        trimmed = self._client.sub("", msg, count=1)
        if trimmed != msg:
            record.msg = trimmed
            record.args = ()
        return True


class GmqttPacketIdMaskFilter(logging.Filter):
    _pattern = re.compile(r"(\[[A-Z0-9 _-]+\])\s+\d+\b")

    def filter(self, record: logging.LogRecord) -> bool:
        name = getattr(record, "name", None)
        if not isinstance(name, str) or not name.startswith("gmqtt"):
            return True

        try:
            msg = record.getMessage()
        except Exception:
            return True

        if not isinstance(msg, str):
            return True

        masked = self._pattern.sub(r"\1 N", msg)
        if masked != msg:
            record.msg = masked
            record.args = ()

        return True


def _build_formatters(log_format: str) -> dict:
    if log_format == LogFormat.PLAIN.value:
        plain_format = "%(levelname)s - %(asctime)s - %(name)s - %(message)s"
        return {
            LogFormat.PLAIN.value: {
                "format": plain_format,
            }
        }

    json_format = "%(asctime)s %(levelname)s %(name)s %(message)s %(funcName)s"

    return {
        LogFormat.JSON.value: {
            "class": "app.configs.logging_config.PepeunitJsonFormatter",
            "format": json_format,
        },
    }


def _build_logging_config(
    raw_level: str | None = None,
    log_format: str | None = None,
) -> dict:
    if raw_level is None:
        raw_level = runtime.get().pu_instance_log_min_level
    if log_format is None:
        log_format = runtime.get().pu_instance_log_format

    formatter_name = log_format

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "uvicorn_access": {
                "()": "app.configs.logging_config.UvicornAccessFilter",
            },
            "gmqtt_mask_packet_id": {
                "()": "app.configs.logging_config.GmqttPacketIdMaskFilter",
            },
        },
        "formatters": _build_formatters(log_format),
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "filters": ["uvicorn_access", "gmqtt_mask_packet_id"],
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


def apply_logging(level: str, log_format: str) -> None:
    dictConfig(_build_logging_config(level, log_format))


LOGGING_CONFIG: Final = _build_logging_config()


def setup_logging() -> None:
    dictConfig(_build_logging_config())
    logging.getLogger(__name__)
