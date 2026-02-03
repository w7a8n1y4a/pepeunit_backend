import logging
import os
import uuid as uuid_pkg

from fastapi import APIRouter, Depends, File, UploadFile, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse, PlainTextResponse

from app.configs.clickhouse import get_hand_clickhouse_client
from app.configs.db import get_hand_session
from app.configs.rest import get_unit_service
from app.dto.enum import BackendTopicCommand
from app.schemas.pydantic.repo import TargetVersionRead
from app.schemas.pydantic.shared import MqttRead
from app.schemas.pydantic.unit import (
    EnvJsonString,
    StateStorage,
    UnitCreate,
    UnitFilter,
    UnitLogFilter,
    UnitLogRead,
    UnitLogsResult,
    UnitMqttTokenAuth,
    UnitRead,
    UnitsResult,
    UnitUpdate,
)
from app.services.unit_service import UnitService

router = APIRouter()


@router.post(
    "",
    response_model=UnitRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: UnitCreate, unit_service: UnitService = Depends(get_unit_service)
):
    return UnitRead(**unit_service.create(data).to_dict())


@router.get("/{uuid}", response_model=UnitRead)
def get(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return UnitRead(**unit_service.get(uuid).to_dict())


@router.get("/env/{uuid}", response_model=dict)
def get_env(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return unit_service.get_env(uuid)


@router.get("/get_target_version/{uuid}", response_model=TargetVersionRead)
def get_target_version(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return unit_service.get_target_version(uuid)


@router.get("/get_current_schema/{uuid}", response_model=dict)
def get_current_schema(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return unit_service.get_current_schema(uuid)


@router.get("/firmware/zip/{uuid}", response_model=bytes)
def get_firmware_zip(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    zip_filepath = unit_service.get_unit_firmware_zip(uuid)

    def cleanup():
        os.remove(zip_filepath)

    return FileResponse(zip_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tar/{uuid}", response_model=bytes)
def get_firmware_tar(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    tar_filepath = unit_service.get_unit_firmware_tar(uuid)

    def cleanup():
        os.remove(tar_filepath)

    return FileResponse(tar_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tgz/{uuid}", response_model=bytes)
def get_firmware_tgz(
    uuid: uuid_pkg.UUID,
    wbits: int = 9,
    level: int = 9,
    unit_service: UnitService = Depends(get_unit_service),
):
    tgz_filepath = unit_service.get_unit_firmware_tgz(uuid, wbits, level)

    def cleanup():
        os.remove(tgz_filepath)

    return FileResponse(tgz_filepath, background=BackgroundTask(cleanup))


@router.post(
    "/set_state_storage/{uuid}", status_code=status.HTTP_204_NO_CONTENT
)
def set_state_storage(
    uuid: uuid_pkg.UUID,
    state: StateStorage,
    unit_service: UnitService = Depends(get_unit_service),
):
    return unit_service.set_state_storage(uuid, state.state)


@router.get("/get_state_storage/{uuid}", response_model=str)
def get_state_storage(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return unit_service.get_state_storage(uuid)


@router.post("/auth", response_model=MqttRead, status_code=status.HTTP_200_OK)
def get_mqtt_auth(data: UnitMqttTokenAuth):
    with get_hand_session() as db, get_hand_clickhouse_client() as cc:
        try:
            unit_service = get_unit_service(db, cc, data.token)
            unit_service.get_mqtt_auth(data.topic)
            db.close()
        except Exception as e:
            logging.info(repr(e))
            return MqttRead(result="deny")

    return MqttRead(result="allow")


@router.patch("/{uuid}", response_model=UnitRead)
def update(
    uuid: uuid_pkg.UUID,
    data: UnitUpdate,
    unit_service: UnitService = Depends(get_unit_service),
):
    return UnitRead(**unit_service.update(uuid, data).to_dict())


@router.post(
    "/send_command_to_input_base_topic/{uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def send_command_to_input_base_topic(
    uuid: uuid_pkg.UUID,
    command: BackendTopicCommand,
    unit_service: UnitService = Depends(get_unit_service),
):
    return unit_service.unit_node_service.command_to_input_base_topic(
        uuid, command
    )


@router.patch("/env/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def set_env(
    uuid: uuid_pkg.UUID,
    env_json_str: EnvJsonString,
    unit_service: UnitService = Depends(get_unit_service),
):
    return unit_service.set_env(uuid, env_json_str.env_json_string)


@router.delete("/env/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def reset_env(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return unit_service.reset_env(uuid)


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    uuid: uuid_pkg.UUID, unit_service: UnitService = Depends(get_unit_service)
):
    return unit_service.delete(uuid)


@router.get("", response_model=UnitsResult)
def get_units(
    filters: UnitFilter = Depends(UnitFilter),
    is_include_output_unit_nodes: bool = False,
    unit_service: UnitService = Depends(get_unit_service),
):
    count, units = unit_service.list(filters, is_include_output_unit_nodes)
    return UnitsResult(
        count=count,
        units=[unit_service.mapper_unit_to_unit_read(unit) for unit in units],
    )


@router.get("/log_list/", response_model=UnitLogsResult)
def get_unit_logs(
    filters: UnitLogFilter = Depends(UnitLogFilter),
    unit_service: UnitService = Depends(get_unit_service),
):
    count, unit_logs = unit_service.log_list(filters)
    return UnitLogsResult(
        count=count,
        unit_logs=[UnitLogRead(**unit_log.dict()) for unit_log in unit_logs],
    )


@router.post(
    "/convert_toml_to_md",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def convert_toml_to_md(
    file: UploadFile = File(...),
    unit_service: UnitService = Depends(get_unit_service),
):
    md = await unit_service.convert_toml_file_to_md(file)
    return PlainTextResponse(content=md, media_type="text/markdown")
