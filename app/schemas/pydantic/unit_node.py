import datetime
import uuid as uuid_pkg
from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel

from app.dto.clickhouse.aggregation import Aggregation
from app.dto.clickhouse.n_records import NRecords
from app.dto.clickhouse.time_window import TimeWindow
from app.dto.enum import (
    AggregationFunctions,
    DataPipeStage,
    OrderByDate,
    ProcessingPolicyType,
    UnitNodeTypeEnum,
    VisibilityLevel,
)
from app.utils.utils import parse_interval


class UnitNodeUpdate(BaseModel):
    visibility_level: VisibilityLevel | None = None
    is_rewritable_input: bool | None = None
    is_data_pipe_active: bool | None = None
    max_connections: int | None = None


class UnitNodeSetState(BaseModel):
    state: str | None = None


@dataclass
class UnitNodeFilter:
    uuids: list[uuid_pkg.UUID] | None = Query([])

    unit_uuid: uuid_pkg.UUID | None = None
    search_string: str | None = None

    type: list[str] | None = Query([item.value for item in UnitNodeTypeEnum])
    visibility_level: list[str] | None = Query(
        [item.value for item in VisibilityLevel]
    )

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    # get only input UnitNode linked with this output UnitNode
    output_uuid: uuid_pkg.UUID | None = None

    def dict(self):
        return self.__dict__


class UnitNodeEdgeRead(BaseModel):
    uuid: uuid_pkg.UUID
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID


class UnitNodeEdgeCreate(BaseModel):
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID


class DataPipeValidationErrorRead(BaseModel):
    stage: DataPipeStage
    message: str


@dataclass
class DataPipeFilter:
    uuid: uuid_pkg.UUID
    type: ProcessingPolicyType

    search_string: str | None = None

    aggregation_type: list[str] | None = Query(
        [item.value for item in AggregationFunctions]
    )
    time_window_size: int | None = None

    start_agg_window_datetime: datetime.datetime | None = None
    end_agg_window_datetime: datetime.datetime | None = None

    start_create_datetime: datetime.datetime | None = None
    end_create_datetime: datetime.datetime | None = None

    relative_time: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    @property
    def relative_interval(self):
        return (
            parse_interval(self.relative_time) if self.relative_time else None
        )

    def dict(self):
        return self.__dict__


class PipeDataResult(BaseModel):
    count: int
    pipe_data: list[NRecords | TimeWindow | Aggregation]
