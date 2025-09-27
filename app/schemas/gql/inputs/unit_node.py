import uuid as uuid_pkg
from datetime import datetime

import strawberry

from app.dto.enum import (
    AggregationFunctions,
    OrderByDate,
    ProcessingPolicyType,
    UnitNodeTypeEnum,
    VisibilityLevel,
)
from app.schemas.gql.type_input_mixin import TypeInputMixin
from app.utils.utils import parse_interval


@strawberry.input()
class UnitNodeUpdateInput(TypeInputMixin):
    visibility_level: VisibilityLevel | None = None
    is_rewritable_input: bool | None = None
    is_data_pipe_active: bool | None = None


@strawberry.input()
class UnitNodeSetStateInput(TypeInputMixin):
    state: str | None = None


@strawberry.input()
class UnitNodeFilterInput(TypeInputMixin):
    uuids: list[uuid_pkg.UUID] | None = ()

    unit_uuid: uuid_pkg.UUID | None = None
    search_string: str | None = None

    type: list[UnitNodeTypeEnum] | None = tuple(UnitNodeTypeEnum)
    visibility_level: list[VisibilityLevel] | None = tuple(VisibilityLevel)

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    # get only input UnitNode linked with this output UnitNode
    output_uuid: uuid_pkg.UUID | None = None


@strawberry.input()
class UnitNodeEdgeCreateInput(TypeInputMixin):
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID


@strawberry.input()
class DataPipeFilterInput(TypeInputMixin):
    uuid: uuid_pkg.UUID
    type: ProcessingPolicyType

    search_string: str | None = None

    aggregation_type: list[AggregationFunctions] | None = tuple(
        AggregationFunctions
    )
    time_window_size: int | None = None

    start_agg_window_datetime: datetime | None = None
    end_agg_window_datetime: datetime | None = None

    start_create_datetime: datetime | None = None
    end_create_datetime: datetime | None = None

    relative_time: str | None = None

    order_by_create_date: OrderByDate | None = OrderByDate.desc

    offset: int | None = None
    limit: int | None = None

    @property
    def relative_interval(self):
        return (
            parse_interval(self.relative_time) if self.relative_time else None
        )
