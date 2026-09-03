import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import (
    get_instance_cache,
    get_instance_service,
)
from app.repositories.instance_cache_repository import InstanceCacheRepository
from app.schemas.pydantic.instance import (
    CurrentInstanceSchemaV1,
    InstanceCreate,
    InstanceFilter,
    InstanceRead,
    InstanceRegistriesPage,
    InstancesPage,
    InstanceUpdate,
    InstanceUrlsPage,
)
from app.services.instance_service import InstanceService

router = APIRouter()


@router.get("/current", response_model=CurrentInstanceSchemaV1)
def get_current_instance(
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    return service.get_cached_current(cache)


@router.get("", response_model=InstancesPage)
def get_instances(
    filters: InstanceFilter = Depends(InstanceFilter),
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    return service.get_cached_instances(cache, filters)


@router.get("/urls", response_model=InstanceUrlsPage)
def get_instance_urls(
    filters: InstanceFilter = Depends(InstanceFilter),
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    return service.get_cached_urls(cache, filters)


@router.get("/registries", response_model=InstanceRegistriesPage)
def get_instance_registries(
    filters: InstanceFilter = Depends(InstanceFilter),
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    return service.get_cached_registries(cache, filters)


@router.post(
    "",
    response_model=InstanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_instance(
    data: InstanceCreate,
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    instance = await service.create(data)
    service.refresh_cache(cache)
    return service.mapper_instance_to_instance_read(instance)


@router.patch("/{instance_uuid}", response_model=InstanceRead)
async def update_instance(
    instance_uuid: uuid_pkg.UUID,
    data: InstanceUpdate,
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    instance = await service.update(instance_uuid, data)
    service.refresh_cache(cache)
    return service.mapper_instance_to_instance_read(instance)


@router.delete(
    "/{instance_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_instance(
    instance_uuid: uuid_pkg.UUID,
    service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    service.delete(instance_uuid)
    service.refresh_cache(cache)


@router.post("/scan", status_code=status.HTTP_204_NO_CONTENT)
def scan_instances(
    instance_service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    instance_service.scan_all(cache)


@router.post(
    "/{instance_uuid}/scan",
    status_code=status.HTTP_204_NO_CONTENT,
)
def scan_instance(
    instance_uuid: uuid_pkg.UUID,
    instance_service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    instance_service.scan_one(instance_uuid, cache)


@router.post(
    "/integration-tests",
    status_code=status.HTTP_204_NO_CONTENT,
)
def run_integration_tests(
    instance_service: InstanceService = Depends(get_instance_service),
    cache: InstanceCacheRepository = Depends(get_instance_cache),
):
    instance_service.start_integration_tests(cache)
