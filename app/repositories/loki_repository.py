import logging
from dataclasses import dataclass
from operator import attrgetter
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError, field_validator

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
    def backend_error_groups(
        self, limit: int = 3
    ) -> list[BackendErrorGroup] | None:
        response = self._response(self._query(limit))
        if response is None:
            return None
        samples = self._samples(response)
        if samples is None:
            return None
        groups = [self._group(sample) for sample in samples]
        return sorted(groups, key=attrgetter("count"), reverse=True)[:limit]

    def _query(self, limit: int) -> str:
        selector = '{app="backend"} | json | level=~"ERROR|CRITICAL"'
        return (
            f"topk({limit}, sum by (message) "
            f"(count_over_time({selector} [24h])))"
        )

    def _response(self, query: str) -> httpx.Response | None:
        try:
            response = httpx.get(
                f"{settings.pu_notification_loki_url.rstrip('/')}/loki/api/v1/query",
                params={"query": query},
                timeout=settings.http_timeout(),
            )
            response.raise_for_status()
        except httpx.HTTPError as err:
            logging.error(f"Loki request failed: {err}")
            return None
        return response

    def _samples(self, response: httpx.Response) -> list[_LokiSample] | None:
        try:
            payload = _LokiQuery.model_validate_json(response.content)
        except ValidationError as err:
            logging.error(f"Loki query failed: {err}")
            return None
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
