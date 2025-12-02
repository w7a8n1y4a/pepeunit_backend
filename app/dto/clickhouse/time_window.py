import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel

from app.dto.enum import TypeInputValue
from app.dto.mixin import ClickHouseBaseMixin


class TimeWindow(BaseModel, ClickHouseBaseMixin):
    unit_node_uuid: uuid_pkg.UUID
    state: str
    state_type: TypeInputValue
    create_datetime: datetime
    expiration_datetime: datetime
    size: int
