import datetime
import uuid as uuid_pkg
from dataclasses import dataclass
from typing import Optional, Union

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
    visibility_level: Optional[VisibilityLevel] = None
    is_rewritable_input: Optional[bool] = None
    is_data_pipe_active: Optional[bool] = None


class UnitNodeSetState(BaseModel):
    state: Optional[str] = None


@dataclass
class UnitNodeFilter:
    uuids: Optional[list[uuid_pkg.UUID]] = Query([])

    unit_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    type: Optional[list[str]] = Query([item.value for item in UnitNodeTypeEnum])
    visibility_level: Optional[list[str]] = Query([item.value for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    # get only input UnitNode linked with this output UnitNode
    output_uuid: Optional[uuid_pkg.UUID] = None

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

    search_string: Optional[str] = None

    aggregation_type: Optional[list[str]] = Query([item.value for item in AggregationFunctions])
    time_window_size: Optional[int] = None

    start_agg_window_datetime: Optional[datetime.datetime] = None
    end_agg_window_datetime: Optional[datetime.datetime] = None

    start_create_datetime: Optional[datetime.datetime] = None
    end_create_datetime: Optional[datetime.datetime] = None

    relative_time: Optional[str] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    @property
    def relative_interval(self):
        return parse_interval(self.relative_time) if self.relative_time else None

    def dict(self):
        return self.__dict__


class PipeDataResult(BaseModel):
    count: int
    pipe_data: list[Union[NRecords, TimeWindow, Aggregation]]
