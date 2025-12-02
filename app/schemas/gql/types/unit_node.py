import uuid as uuid_pkg
from datetime import datetime

import strawberry

from app.dto.enum import AggregationFunctions, DataPipeStage, TypeInputValue
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class UnitNodeEdgeType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID
    creator_uuid: strawberry.Private[object]


@strawberry.type()
class DataPipeValidationErrorType(TypeInputMixin):
    stage: DataPipeStage
    message: str


@strawberry.type()
class NRecordsType(TypeInputMixin):
    unit_node_uuid: uuid_pkg.UUID
    state: str
    state_type: TypeInputValue
    create_datetime: datetime
    max_count: int
    size: int


@strawberry.type()
class TimeWindowType(TypeInputMixin):
    unit_node_uuid: uuid_pkg.UUID
    state: str
    state_type: TypeInputValue
    create_datetime: datetime
    expiration_datetime: datetime
    size: int


@strawberry.type()
class AggregationType(TypeInputMixin):
    unit_node_uuid: uuid_pkg.UUID
    state: float
    aggregation_type: AggregationFunctions
    time_window_size: int
    create_datetime: datetime
    start_window_datetime: datetime


@strawberry.type()
class LastValueType(TypeInputMixin):
    unit_node_uuid: uuid_pkg.UUID
    state: str
    last_update_datetime: datetime


@strawberry.type()
class PipeDataResultType(TypeInputMixin):
    count: int
    pipe_data: list[
        NRecordsType | TimeWindowType | AggregationType | LastValueType
    ]
