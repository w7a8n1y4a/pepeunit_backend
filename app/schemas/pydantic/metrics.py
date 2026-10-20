from pydantic import BaseModel


class BaseMetricsRead(BaseModel):
    user_count: int
    repository_registry_count: int
    unit_count: int
    unit_io_count: int
    unit_io_edge_count: int
