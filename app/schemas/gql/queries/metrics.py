import strawberry
from strawberry.types import Info

from app.configs.gql import get_metrics_service
from app.schemas.gql.types.metrics import BaseMetricsType


@strawberry.field()
def get_base_metrics(info: Info) -> BaseMetricsType:
    unit_node_service = get_metrics_service(info)
    return BaseMetricsType(**unit_node_service.get_instance_metrics().dict())
