import strawberry

from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class BaseMetricsType(TypeInputMixin):
    user_count: int
    repo_count: int
    unit_count: int
    unit_node_count: int
