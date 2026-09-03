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
    urls: InstanceUrlsPage
    registries: InstanceRegistriesPage
    last_ping: float


class InstanceExternalRepository:
    async def collect(self, current_url: str) -> CollectedInstance:
        started_at = time.perf_counter()
        state, urls, registries = await asyncio.gather(
            self._get_current(current_url),
            self._get_urls(current_url),
            self._get_registries(current_url),
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

    async def _get_urls(self, current_url: str) -> InstanceUrlsPage:
        urls: list[str] = []
        endpoint = f"{current_url.rsplit('/', 1)[0]}/urls"
        while True:
            response = await self._request(
                endpoint,
                httpx.QueryParams(
                    offset=len(urls),
                    limit=settings.pu_max_pagination_size,
                ),
            )
            page = InstanceUrlsPage.model_validate_json(response.content)
            urls.extend(page.urls)
            if not page.urls or len(urls) >= page.total_count:
                return InstanceUrlsPage(
                    total_count=page.total_count,
                    urls=urls,
                )

    async def _get_registries(
        self,
        current_url: str,
    ) -> InstanceRegistriesPage:
        registries: list[InstancePublicRegistry] = []
        endpoint = f"{current_url.rsplit('/', 1)[0]}/registries"
        while True:
            response = await self._request(
                endpoint,
                httpx.QueryParams(
                    offset=len(registries),
                    limit=settings.pu_max_pagination_size,
                ),
            )
            page = InstanceRegistriesPage.model_validate_json(response.content)
            registries.extend(page.registries)
            if not page.registries or len(registries) >= page.total_count:
                return InstanceRegistriesPage(
                    total_count=page.total_count,
                    registries=registries,
                )

    async def _request(
        self,
        url: str,
        params: httpx.QueryParams | None = None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=settings.pu_instance_request_timeout,
        ) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        if len(response.content) > settings.pu_instance_max_state_size:
            msg = "Collected instance response exceeds the size limit"
            raise ValueError(msg)
        return response
