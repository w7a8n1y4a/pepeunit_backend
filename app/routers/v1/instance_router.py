import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_instance_service
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
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.get_cached_current()


@router.get("", response_model=InstancesPage)
def get_instances(
    filters: InstanceFilter = Depends(InstanceFilter),
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.get_cached_instances(filters)


@router.get("/urls", response_model=InstanceUrlsPage)
def get_instance_urls(
    filters: InstanceFilter = Depends(InstanceFilter),
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.get_cached_urls(filters)


@router.get("/registries", response_model=InstanceRegistriesPage)
def get_instance_registries(
    filters: InstanceFilter = Depends(InstanceFilter),
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.get_cached_registries(filters)


@router.post(
    "",
    response_model=InstanceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_instance(
    data: InstanceCreate,
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.mapper_instance_to_instance_read(
        instance_service.create(data)
    )


@router.patch("/{uuid}", response_model=InstanceRead)
def update_instance(
    uuid: uuid_pkg.UUID,
    data: InstanceUpdate,
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.mapper_instance_to_instance_read(
        instance_service.update(uuid, data)
    )


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(
    uuid: uuid_pkg.UUID,
    instance_service: InstanceService = Depends(get_instance_service),
):
    instance_service.delete(uuid)


@router.post("/scan_all", status_code=status.HTTP_204_NO_CONTENT)
def scan_instances(
    instance_service: InstanceService = Depends(get_instance_service),
):
    instance_service.scan_all()


@router.post("/scan/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def scan_instance(
    uuid: uuid_pkg.UUID,
    instance_service: InstanceService = Depends(get_instance_service),
):
    instance_service.scan_one(uuid)


@router.post("/integration_tests", status_code=status.HTTP_204_NO_CONTENT)
def run_integration_tests(
    instance_service: InstanceService = Depends(get_instance_service),
):
    instance_service.start_integration_tests()
