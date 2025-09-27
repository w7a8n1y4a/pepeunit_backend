import os
import uuid as uuid_pkg

import strawberry
from strawberry.file_uploads import Upload
from strawberry.types import Info

from app.configs.errors import DataPipeError
from app.configs.gql import get_unit_node_service_gql
from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.last_value import LastValue
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.time_window import TimeWindow
from app.schemas.gql.inputs.unit_node import (
    DataPipeFilterInput,
    UnitNodeFilterInput,
)
from app.schemas.gql.types.shared import UnitNodesResultType, UnitNodeType
from app.schemas.gql.types.unit_node import (
    AggregationType,
    DataPipeValidationErrorType,
    LastValueType,
    NRecordsType,
    PipeDataResultType,
    TimeWindowType,
)


@strawberry.field()
def get_unit_node(uuid: uuid_pkg.UUID, info: Info) -> UnitNodeType:
    unit_node_service = get_unit_node_service_gql(info)
    return UnitNodeType(**unit_node_service.get(uuid).dict())


@strawberry.field()
def get_pipe_data(
    filters: DataPipeFilterInput, info: Info
) -> PipeDataResultType:
    unit_node_service = get_unit_node_service_gql(info)
    count, pipe_data = unit_node_service.get_data_pipe_data(filters)

    def get_gql_type(
        input_value: NRecords | TimeWindow | Aggregation | LastValue,
    ) -> NRecordsType | TimeWindowType | AggregationType:
        if isinstance(input_value, NRecords):
            return NRecordsType
        if isinstance(input_value, TimeWindow):
            return TimeWindowType
        if isinstance(input_value, Aggregation):
            return AggregationType
        if isinstance(input_value, LastValue):
            return LastValueType
        msg = "Other types are not supported"
        raise DataPipeError(msg)

    return PipeDataResultType(
        count=count,
        pipe_data=[get_gql_type(value)(**value.dict()) for value in pipe_data],
    )


@strawberry.field()
def get_unit_nodes(
    filters: UnitNodeFilterInput, info: Info
) -> UnitNodesResultType:
    unit_node_service = get_unit_node_service_gql(info)
    count, unit_nodes = unit_node_service.list(filters)
    return UnitNodesResultType(
        count=count,
        unit_nodes=[
            UnitNodeType(**unit_node.dict()) for unit_node in unit_nodes
        ],
    )


@strawberry.field()
async def check_data_pipe_config(
    file: Upload, info: Info
) -> list[DataPipeValidationErrorType]:
    unit_node_service = get_unit_node_service_gql(info)
    return [
        DataPipeValidationErrorType(**item.dict())
        for item in await unit_node_service.check_data_pipe_config(file)
    ]


@strawberry.field()
def get_data_pipe_config(uuid: uuid_pkg.UUID, info: Info) -> str:
    unit_node_service = get_unit_node_service_gql(info)
    yml_filepath = unit_node_service.get_data_pipe_config(uuid)

    with open(yml_filepath) as f:
        file_data = f.read()

    os.remove(yml_filepath)

    return file_data
