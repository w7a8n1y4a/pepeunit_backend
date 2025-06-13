import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel

from app.dto.enum import TypeInputValue
from app.dto.mixin import ClickHouseBaseMixin


class NRecords(BaseModel, ClickHouseBaseMixin):
    id: int
    uuid: uuid_pkg.UUID
    unit_node_uuid: uuid_pkg.UUID
    state: str
    state_type: TypeInputValue
    create_datetime: datetime
    max_count: int
    size: int
