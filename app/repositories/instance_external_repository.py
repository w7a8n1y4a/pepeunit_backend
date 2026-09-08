import asyncio
import time
from dataclasses import dataclass

import httpx

from app import settings
from app.schemas.pydantic.instance import (
    CurrentInstanceSchemaV1,
    InstancePublicRegistry,
    InstanceRegistriesPage,
    InstanceUrlsPage,
)


@dataclass
class CollectedInstance:
    state: CurrentInstanceSchemaV1
    urls: list[str]
    registries: list[InstancePublicRegistry]
    last_ping: float


class InstanceExternalRepository:
    async def collect(self, current_url: str) -> CollectedInstance:
        started_at = time.perf_counter()
        state, urls, registries = await asyncio.gather(
            self._get_current(current_url),
            self._get_all_items(current_url, "urls", InstanceUrlsPage, "urls"),
            self._get_all_items(
                current_url,
                "registries",
                InstanceRegistriesPage,
                "registries",
            ),
        )
        return CollectedInstance(
            state=state,
            urls=urls,
            registries=registries,
            last_ping=round((time.perf_counter() - started_at) * 1000, 3),
        )

    async def _get_current(self, current_url: str) -> CurrentInstanceSchemaV1:
        response = await self._request(current_url)
        return CurrentInstanceSchemaV1.model_validate_json(response.content)

    async def _get_all_items(
        self,
        current_url: str,
        endpoint: str,
        page_model: type[InstanceUrlsPage] | type[InstanceRegistriesPage],
        items_field: str,
    ) -> list:
        url = f"{current_url.rsplit('/', 1)[0]}/{endpoint}"

        items = []
        while True:
            response = await self._request(
                url,
                httpx.QueryParams(
                    offset=len(items),
                    limit=settings.pu_max_pagination_size,
                ),
            )
            page = page_model.model_validate_json(response.content)

            page_items = getattr(page, items_field)
            items.extend(page_items)
            if not page_items or len(items) >= page.total_count:
                return items

    async def _request(
        self,
        url: str,
        params: httpx.QueryParams | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=settings.http_timeout(),
        ) as client:
            response = await client.get(url, params=params)

        response.raise_for_status()
        self.is_valid_response_size(response)
        return response

    @staticmethod
    def is_valid_response_size(response: httpx.Response) -> None:
        if len(response.content) > settings.pu_instance_max_state_size:
            msg = f"Instance response {len(response.content)} B exceeds the limit {settings.pu_instance_max_state_size} B"
            raise ValueError(msg)
