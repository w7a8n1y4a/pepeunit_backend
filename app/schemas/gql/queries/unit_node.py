import uuid as uuid_pkg

import strawberry
from strawberry.file_uploads import Upload
from strawberry.types import Info

from app.configs.gql import get_unit_node_service_gql
from app.schemas.gql.inputs.unit_node import UnitNodeFilterInput
from app.schemas.gql.types.shared import UnitNodesResultType, UnitNodeType
from app.schemas.gql.types.unit_node import DataPipeValidationErrorType


@strawberry.field()
def get_unit_node(uuid: uuid_pkg.UUID, info: Info) -> UnitNodeType:
    unit_node_service = get_unit_node_service_gql(info)
    return UnitNodeType(**unit_node_service.get(uuid).dict())


@strawberry.field()
def get_unit_nodes(filters: UnitNodeFilterInput, info: Info) -> UnitNodesResultType:
    unit_node_service = get_unit_node_service_gql(info)
    count, unit_nodes = unit_node_service.list(filters)
    return UnitNodesResultType(count=count, unit_nodes=[UnitNodeType(**unit_node.dict()) for unit_node in unit_nodes])


@strawberry.field()
async def check_data_pipe_config(file: Upload, info: Info) -> list[DataPipeValidationErrorType]:
    unit_node_service = get_unit_node_service_gql(info)
    return [DataPipeValidationErrorType(**item.dict()) for item in await unit_node_service.check_data_pipe_config(file)]
