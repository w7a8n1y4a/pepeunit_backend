import logging

import httpx

from app import settings

# Same shape as the backend aggregated logs dashboard, capped at three groups
_QUERY = (
    "topk({limit}, sum by (message) "
    '(count_over_time({{app="backend"}} | json | '
    'level=~"ERROR|CRITICAL" [24h])))'
)
_EXCERPT_LIMIT = 80


def query_backend_error_groups(limit: int = 3) -> list[dict]:
    """Top backend error groups from Loki for the last 24 hours.

    A failed query leaves the daily state with metrics and an empty list.
    """
    try:
        response = httpx.get(
            f"{settings.pu_loki_url.rstrip('/')}/loki/api/v1/query",
            params={"query": _QUERY.format(limit=limit)},
            timeout=settings.http_timeout(),
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logging.exception("Failed to read backend errors from Loki")
        return []

    if payload.get("status") != "success":
        logging.error("Loki query failed: %s", payload)
        return []

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
        groups.append({"count": count, "message": _excerpt(message)})

    groups.sort(key=lambda item: item["count"], reverse=True)
    return groups[:limit]


def _excerpt(message: str) -> str:
    text = " ".join(message.split())
    if len(text) <= _EXCERPT_LIMIT:
        return text
    return text[: _EXCERPT_LIMIT - 1] + "…"
