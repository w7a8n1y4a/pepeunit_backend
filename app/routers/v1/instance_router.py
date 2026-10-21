from fastapi import APIRouter, Depends, status

from app.configs.rest import (
    get_instance_settings_service,
    get_peer_service,
)
from app.schemas.pydantic.instance import CurrentInstanceSchemaV1
from app.schemas.pydantic.instance_settings import (
    InstanceSettingsRead,
    InstanceSettingsUpdate,
)
from app.services.instance_settings_service import InstanceSettingsService
from app.services.peer_service import PeerService

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
    peer_service: PeerService = Depends(get_peer_service),
):
    return peer_service.get_cached_current()


@router.post("/integration_tests", status_code=status.HTTP_204_NO_CONTENT)
def run_integration_tests(
    peer_service: PeerService = Depends(get_peer_service),
):
    peer_service.start_integration_tests()
