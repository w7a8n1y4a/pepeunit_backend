"""Serialize every API datetime as UTC.

Database columns are timestamp without time zone. Those values are UTC,
but a naive ISO string is read as local time by browsers. JSON output
therefore always carries the Zulu suffix.
"""

from datetime import UTC, datetime
from typing import ClassVar

from fastapi.encoders import ENCODERS_BY_TYPE
from pydantic_core import core_schema


class UtcJson:
    _offset_suffix: ClassVar[str] = "+00:00"
    _installed: ClassVar[bool] = False
    _original_datetime_schema: ClassVar = core_schema.datetime_schema

    @classmethod
    def format_datetime(cls, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        text = value.isoformat()
        if text.endswith(cls._offset_suffix):
            return f"{text[: -len(cls._offset_suffix)]}Z"
        return text

    @classmethod
    def _datetime_schema(cls, *args, **kwargs):
        schema = cls._original_datetime_schema(*args, **kwargs)
        if kwargs.get("serialization") is None:
            schema["serialization"] = (
                core_schema.plain_serializer_function_ser_schema(
                    cls.format_datetime,
                    when_used="json",
                    return_schema=core_schema.str_schema(),
                )
            )
        return schema

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return

        core_schema.datetime_schema = cls._datetime_schema
        ENCODERS_BY_TYPE[datetime] = cls.format_datetime
        cls._installed = True
