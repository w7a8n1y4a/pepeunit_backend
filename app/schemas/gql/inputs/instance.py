import strawberry

from app.dto.enum import InstanceTrustStatus
from app.schemas.gql.type_input_mixin import BasePaginationGql, TypeInputMixin


@strawberry.input()
class InstanceCreateInput(TypeInputMixin):
    url: str


@strawberry.input()
class InstanceUpdateInput(TypeInputMixin):
    trust_status: InstanceTrustStatus


@strawberry.input()
class InstanceFilterInput(BasePaginationGql):
    pass
