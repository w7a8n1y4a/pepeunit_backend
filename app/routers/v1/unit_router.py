import json
import logging
import os

from fastapi import APIRouter, Depends, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.configs.db import get_session
from app.configs.gql import get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.schemas.pydantic.shared import MqttRead
from app.schemas.pydantic.unit import UnitCreate, UnitUpdate, UnitFilter, UnitRead, UnitMqttTokenAuth
from app.services.unit_service import UnitService
from app.services.validators import is_valid_uuid

router = APIRouter()


@router.post(
    "",
    response_model=UnitRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: UnitCreate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.create(data).dict())


@router.get("/{uuid}", response_model=UnitRead)
def get(uuid: str, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.get(is_valid_uuid(uuid)).dict())


@router.get("/env/{uuid}", response_model=str)
def get_env(uuid: str, unit_service: UnitService = Depends()):
    return json.dumps(unit_service.get_env(is_valid_uuid(uuid)))


@router.get("/get_current_schema/{uuid}", response_model=str)
def get_current_schema(uuid: str, unit_service: UnitService = Depends()):
    return json.dumps(unit_service.get_current_schema(is_valid_uuid(uuid)))


@router.get("/firmware/zip/{uuid}", response_model=bytes)
def get_firmware_zip(uuid: str, unit_service: UnitService = Depends()):
    zip_filepath = unit_service.get_unit_firmware_zip(is_valid_uuid(uuid))

    def cleanup():
        os.remove(zip_filepath)

    return FileResponse(zip_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tar/{uuid}", response_model=bytes)
def get_firmware_tar(uuid: str, unit_service: UnitService = Depends()):
    tar_filepath = unit_service.get_unit_firmware_tar(is_valid_uuid(uuid))

    def cleanup():
        os.remove(tar_filepath)

    return FileResponse(tar_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tgz/{uuid}", response_model=bytes)
def get_firmware_tgz(uuid: str, wbits: int = 9, level: int = 9, unit_service: UnitService = Depends()):
    tgz_filepath = unit_service.get_unit_firmware_tgz(is_valid_uuid(uuid), wbits, level)

    def cleanup():
        os.remove(tgz_filepath)

    return FileResponse(tgz_filepath, background=BackgroundTask(cleanup))


@router.post("/auth", response_model=MqttRead, status_code=status.HTTP_200_OK)
def get_mqtt_auth(data: UnitMqttTokenAuth):

    db = next(get_session())
    try:
        unit_service = get_unit_service(InfoSubEntity({'db': db, 'jwt_token': data.token}))
        unit_service.get_mqtt_auth(data.topic)
        db.close()
    except Exception as e:
        logging.info(repr(e))
        db.close()
        return MqttRead(result='deny')

    return MqttRead(result='allow')


@router.patch("/{uuid}", response_model=UnitRead)
def update(uuid: str, data: UnitUpdate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.update(is_valid_uuid(uuid), data).dict())


@router.post("/update_schema/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def update_schema(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.update_schema(is_valid_uuid(uuid))


@router.patch("/env/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def set_env(uuid: str, env_json_str: str, unit_service: UnitService = Depends()):
    return unit_service.set_env(is_valid_uuid(uuid), env_json_str)


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.delete(is_valid_uuid(uuid))


@router.get("", response_model=list[UnitRead])
def get_units(filters: UnitFilter = Depends(UnitFilter), unit_service: UnitService = Depends()):
    return [UnitRead(**unit.dict()) for unit in unit_service.list(filters)]
