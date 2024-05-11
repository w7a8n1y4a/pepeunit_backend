from pydantic import BaseModel


class BaseMetricsRead(BaseModel):
    user_count: int
    repo_count: int
    unit_count: int
    unit_node_count: int
