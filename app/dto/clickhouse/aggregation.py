import uuid as uuid_pkg
from datetime import datetime

from pydantic import BaseModel

from app.dto.enum import AggregationFunctions
from app.dto.mixin import ClickHouseBaseMixin


class Aggregation(BaseModel, ClickHouseBaseMixin):
    uuid: uuid_pkg.UUID
    unit_node_uuid: uuid_pkg.UUID
    state: float
    aggregation_type: AggregationFunctions
    time_window_size: int
    create_datetime: datetime
    start_window_datetime: datetime
    end_window_datetime: datetime
