import uuid as uuid_pkg
from datetime import UTC, datetime

from pydantic import BaseModel

from app.dto.enum import LogLevel
from app.dto.mixin import ClickHouseBaseMixin


class UnitLog(BaseModel, ClickHouseBaseMixin):
    uuid: uuid_pkg.UUID
    level: LogLevel
    unit_uuid: uuid_pkg.UUID
    text: str
    create_datetime: datetime
    expiration_datetime: datetime

    def to_log_line(self) -> str:
        dt = self.create_datetime
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)

        timestamp = (
            f"{dt.strftime('%Y-%m-%d %H:%M:%S')},{dt.microsecond // 1000:03d}"
        )
        return f"{self.level.value.upper()} - {timestamp} - {self.text}"
