import logging

import httpx

from app import settings


class LokiRepository:
    QUERY = (
        "topk({limit}, sum by (message) "
        '(count_over_time({{app="backend"}} | json | '
        'level=~"ERROR|CRITICAL" [24h])))'
    )
    EXCERPT_LIMIT = 80

    def query_backend_error_groups(self, limit: int = 3) -> list[dict] | None:
        try:
            response = httpx.get(
                f"{settings.pu_loki_url.rstrip('/')}/loki/api/v1/query",
                params={"query": self.QUERY.format(limit=limit)},
                timeout=settings.http_timeout(),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logging.exception("Failed to read backend errors from Loki")
            return None

        if payload.get("status") != "success":
            logging.error("Loki query failed: %s", payload)
            return None

        groups = []
        for item in payload.get("data", {}).get("result") or []:
            metric = item.get("metric") or {}
            message = metric.get("message")
            value = item.get("value") or []
            if not isinstance(message, str) or len(value) < 2:
                continue
            try:
                count = int(float(value[1]))
            except TypeError, ValueError:
                continue
            groups.append({"count": count, "message": self._excerpt(message)})

        groups.sort(key=lambda item: item["count"], reverse=True)
        return groups[:limit]

    def _excerpt(self, message: str) -> str:
        text = " ".join(message.split())
        if len(text) <= self.EXCERPT_LIMIT:
            return text
        return text[: self.EXCERPT_LIMIT - 1] + "…"
