import logging
from dataclasses import dataclass
from operator import attrgetter

import httpx

from app import settings


@dataclass(frozen=True)
class BackendErrorGroup:
    count: int
    message: str


class LokiRepository:
    def query_backend_error_groups(
        self, limit: int = 3
    ) -> list[BackendErrorGroup] | None:
        try:
            samples = self._fetch_samples(limit)
        except Exception:
            logging.exception("Failed to read backend errors from Loki")
            return None

        groups = sorted(
            self._groups(samples), key=attrgetter("count"), reverse=True
        )
        return groups[:limit]

    def _query(self, limit: int) -> str:
        selector = '{app="backend"} | json | level=~"ERROR|CRITICAL"'
        return (
            f"topk({limit}, sum by (message) "
            f"(count_over_time({selector} [24h])))"
        )

    def _fetch_samples(self, limit: int) -> list[dict]:
        response = httpx.get(
            f"{settings.pu_loki_url.rstrip('/')}/loki/api/v1/query",
            params={"query": self._query(limit)},
            timeout=settings.http_timeout(),
        )
        response.raise_for_status()

        payload = response.json()
        samples = payload["data"]["result"]
        if payload["status"] != "success" or not isinstance(samples, list):
            logging.error("Loki query failed: %s", payload)
            msg = "Loki query failed"
            raise ValueError(msg)
        return samples

    def _groups(self, samples: list[dict]) -> list[BackendErrorGroup]:
        groups = []
        for sample in samples:
            group = self._group(sample)
            if group is not None:
                groups.append(group)
        return groups

    def _group(self, sample: dict) -> BackendErrorGroup | None:
        try:
            message = sample["metric"]["message"]
            count = int(float(sample["value"][1]))
        except KeyError, IndexError, TypeError, ValueError:
            return None
        if not isinstance(message, str):
            return None
        return BackendErrorGroup(count=count, message=self._excerpt(message))

    def _excerpt(self, message: str) -> str:
        text = " ".join(message.split())
        limit = 80
        if len(text) <= limit:
            return text
        return text[: limit - 1] + "…"
