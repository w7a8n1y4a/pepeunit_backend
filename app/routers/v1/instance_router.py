import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import (
    get_instance_service,
    get_instance_settings_service,
)
from app.schemas.pydantic.instance import (
    CurrentInstanceSchemaV1,
    InstanceCreate,
    InstanceFilter,
    InstanceRead,
    InstanceReposPage,
    InstancesPage,
    InstanceUpdate,
    InstanceUrlsPage,
)
from app.schemas.pydantic.instance_settings import (
    InstanceSettingsRead,
    InstanceSettingsUpdate,
)
from app.services.instance_service import InstanceService
from app.services.instance_settings_service import InstanceSettingsService

router = APIRouter()


@router.get("/settings", response_model=InstanceSettingsRead)
def get_instance_settings(
    instance_settings_service: InstanceSettingsService = Depends(
        get_instance_settings_service
    ),
):
    return instance_settings_service.get()


@router.patch("/settings", response_model=InstanceSettingsRead)
def update_instance_settings(
    data: InstanceSettingsUpdate,
    instance_settings_service: InstanceSettingsService = Depends(
        get_instance_settings_service
    ),
):
    return instance_settings_service.update(data)


@router.post("/reboot", status_code=status.HTTP_204_NO_CONTENT)
def reboot_instance(
    instance_settings_service: InstanceSettingsService = Depends(
        get_instance_settings_service
    ),
):
    instance_settings_service.reboot()


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


@router.get("/repos", response_model=InstanceReposPage)
def get_instance_repos(
    filters: InstanceFilter = Depends(InstanceFilter),
    instance_service: InstanceService = Depends(get_instance_service),
):
    return instance_service.get_cached_repos(filters)


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
