import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry

from app.dto.enum import AggregationFunctions, OrderByDate, ProcessingPolicyType, UnitNodeTypeEnum, VisibilityLevel
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.input()
class UnitNodeUpdateInput(TypeInputMixin):
    visibility_level: Optional[VisibilityLevel] = None
    is_rewritable_input: Optional[bool] = None
    is_data_pipe_active: Optional[bool] = None


@strawberry.input()
class UnitNodeSetStateInput(TypeInputMixin):
    state: Optional[str] = None


@strawberry.input()
class UnitNodeFilterInput(TypeInputMixin):
    uuids: Optional[list[uuid_pkg.UUID]] = tuple()

    unit_uuid: Optional[uuid_pkg.UUID] = None
    search_string: Optional[str] = None

    type: Optional[list[UnitNodeTypeEnum]] = tuple([item for item in UnitNodeTypeEnum])
    visibility_level: Optional[list[VisibilityLevel]] = tuple([item for item in VisibilityLevel])

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None

    # get only input UnitNode linked with this output UnitNode
    output_uuid: Optional[uuid_pkg.UUID] = None


@strawberry.input()
class UnitNodeEdgeCreateInput(TypeInputMixin):
    node_output_uuid: uuid_pkg.UUID
    node_input_uuid: uuid_pkg.UUID


@strawberry.input()
class DataPipeFilterInput(TypeInputMixin):
    uuid: uuid_pkg.UUID
    type: ProcessingPolicyType

    search_string: Optional[str] = None

    aggregation_type: Optional[list[AggregationFunctions]] = tuple([item for item in AggregationFunctions])
    time_window_size: Optional[int] = None

    start_agg_window_datetime: Optional[datetime] = None
    end_agg_window_datetime: Optional[datetime] = None

    start_create_datetime: Optional[datetime] = None
    end_create_datetime: Optional[datetime] = None

    order_by_create_date: Optional[OrderByDate] = OrderByDate.desc

    offset: Optional[int] = None
    limit: Optional[int] = None
