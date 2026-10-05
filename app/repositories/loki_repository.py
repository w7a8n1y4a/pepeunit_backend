from dataclasses import dataclass
from operator import attrgetter
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError, field_validator

from app import settings
from app.configs.errors import LokiError


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
    def query_backend_error_groups(
        self, limit: int = 3
    ) -> list[BackendErrorGroup]:
        response = self._get(self._query(limit))
        groups = [self._group(sample) for sample in self._samples(response)]
        return sorted(groups, key=attrgetter("count"), reverse=True)[:limit]

    def _query(self, limit: int) -> str:
        selector = '{app="backend"} | json | level=~"ERROR|CRITICAL"'
        return (
            f"topk({limit}, sum by (message) "
            f"(count_over_time({selector} [24h])))"
        )

    def _get(self, query: str) -> httpx.Response:
        try:
            response = httpx.get(
                f"{settings.pu_loki_url.rstrip('/')}/loki/api/v1/query",
                params={"query": query},
                timeout=settings.http_timeout(),
            )
            response.raise_for_status()
        except httpx.TimeoutException as err:
            msg = "Loki request timed out"
            raise LokiError(msg) from err
        except httpx.HTTPError as err:
            msg = "Loki request failed"
            raise LokiError(msg) from err
        return response

    def _samples(self, response: httpx.Response) -> list[_LokiSample]:
        try:
            payload = _LokiQuery.model_validate_json(response.content)
        except ValidationError as err:
            msg = "Loki query failed"
            raise LokiError(msg) from err
        return payload.data.result

    def _group(self, sample: _LokiSample) -> BackendErrorGroup:
        return BackendErrorGroup(
            count=int(float(sample.value[1])),
            message=self._excerpt(sample.metric.message),
        )

    def _excerpt(self, message: str) -> str:
        text = " ".join(message.split())
        limit = 80
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"
