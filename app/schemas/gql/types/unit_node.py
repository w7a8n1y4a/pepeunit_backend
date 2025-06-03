import uuid as uuid_pkg

import strawberry

from app.dto.enum import DataPipeStage
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
