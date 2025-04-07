import uuid as uuid_pkg
from datetime import datetime

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
