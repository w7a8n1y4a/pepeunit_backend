import json
import logging
import os
import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.configs.db import get_session
from app.configs.gql import get_unit_service
from app.configs.sub_entities import InfoSubEntity
from app.repositories.enum import BackendTopicCommand
from app.schemas.pydantic.repo import TargetVersionRead
from app.schemas.pydantic.shared import MqttRead
from app.schemas.pydantic.unit import UnitCreate, UnitFilter, UnitMqttTokenAuth, UnitRead, UnitsResult, UnitUpdate
from app.services.unit_service import UnitService

router = APIRouter()


@router.post(
    "",
    response_model=UnitRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: UnitCreate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.create(data).dict())


@router.get("/{uuid}", response_model=UnitRead)
def get(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.get(uuid).dict())


@router.get("/env/{uuid}", response_model=str)
def get_env(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    return json.dumps(unit_service.get_env(uuid))


@router.get("/get_target_version/{uuid}", response_model=TargetVersionRead)
def get_target_version(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    return unit_service.get_target_version(uuid)


@router.get("/get_current_schema/{uuid}", response_model=str)
def get_current_schema(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    return json.dumps(unit_service.get_current_schema(uuid))


@router.get("/firmware/zip/{uuid}", response_model=bytes)
def get_firmware_zip(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    zip_filepath = unit_service.get_unit_firmware_zip(uuid)

    def cleanup():
        os.remove(zip_filepath)

    return FileResponse(zip_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tar/{uuid}", response_model=bytes)
def get_firmware_tar(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    tar_filepath = unit_service.get_unit_firmware_tar(uuid)

    def cleanup():
        os.remove(tar_filepath)

    return FileResponse(tar_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tgz/{uuid}", response_model=bytes)
def get_firmware_tgz(uuid: uuid_pkg.UUID, wbits: int = 9, level: int = 9, unit_service: UnitService = Depends()):
    tgz_filepath = unit_service.get_unit_firmware_tgz(uuid, wbits, level)

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
def update(uuid: uuid_pkg.UUID, data: UnitUpdate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.update(uuid, data).dict())


@router.post("/send_command_to_input_base_topic/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def send_command_to_input_base_topic(
    uuid: uuid_pkg.UUID, command: BackendTopicCommand, unit_service: UnitService = Depends()
):
    return unit_service.command_to_input_base_topic(uuid, command)


@router.patch("/env/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def set_env(uuid: uuid_pkg.UUID, env_json_str: str, unit_service: UnitService = Depends()):
    return unit_service.set_env(uuid, env_json_str)


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: uuid_pkg.UUID, unit_service: UnitService = Depends()):
    return unit_service.delete(uuid)


@router.get("", response_model=UnitsResult)
def get_units(
    filters: UnitFilter = Depends(UnitFilter),
    is_include_output_unit_nodes: bool = False,
    unit_service: UnitService = Depends(),
):
    count, units = unit_service.list(filters, is_include_output_unit_nodes)
    return UnitsResult(count=count, units=[unit_service.mapper_unit_to_unit_read(unit) for unit in units])
