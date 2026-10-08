from dataclasses import dataclass
from operator import attrgetter
from typing import Literal

import httpx
from pydantic import BaseModel, field_validator

from app import settings


@dataclass(frozen=True)
class BackendErrorGroup:
    count: int
    message: str


class _LokiMetric(BaseModel):
    message: str


class _LokiSample(BaseModel):
    metric: _LokiMetric
    value: tuple[float, str]

    @field_validator("value")
    @classmethod
    def count_is_number(cls, value: tuple[float, str]) -> tuple[float, str]:
        int(float(value[1]))
        return value


class _LokiData(BaseModel):
    result: list[_LokiSample]


class _LokiQuery(BaseModel):
    status: Literal["success"]
    data: _LokiData


class LokiRepository:
    def backend_error_groups(self, limit: int = 3) -> list[BackendErrorGroup]:
        selector = '{app="backend"} | json | level=~"ERROR|CRITICAL"'
        query = (
            f"topk({limit}, sum by (message) "
            f"(count_over_time({selector} [24h])))"
        )
        response = httpx.get(
            f"{settings.pu_notification_loki_url.rstrip('/')}/loki/api/v1/query",
            params={"query": query},
            timeout=settings.http_timeout(),
        )
        response.raise_for_status()
        payload = _LokiQuery.model_validate_json(response.content)

        groups = []
        for sample in payload.data.result:
            text = " ".join(sample.metric.message.split())
            if len(text) > 80:
                text = text[:79] + "…"
            groups.append(
                BackendErrorGroup(
                    count=int(float(sample.value[1])),
                    message=text,
                )
            )
        return sorted(groups, key=attrgetter("count"), reverse=True)[:limit]
