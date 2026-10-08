import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel

from app.dto.enum import LogLevel
from app.dto.mixin import ClickHouseBaseMixin
from app.utils.utils import naive_utc


class UnitErrorCount(BaseModel):
    unit_uuid: uuid_pkg.UUID
    count: int


class UnitLog(BaseModel, ClickHouseBaseMixin):
    uuid: uuid_pkg.UUID
    level: LogLevel
    unit_uuid: uuid_pkg.UUID
    text: str
    create_datetime: datetime
    expiration_datetime: datetime

    def to_log_line(self) -> str:
        dt = naive_utc(self.create_datetime)
        timestamp = (
            f"{dt.strftime('%Y-%m-%d %H:%M:%S')},{dt.microsecond // 1000:03d}"
        )
        return f"{self.level.value.upper()} - {timestamp} - {self.text}"
