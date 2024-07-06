import json
import os

from fastapi import APIRouter, Depends, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.configs.db import get_session
from app.domain.unit_model import Unit
from app.domain.unit_node_model import UnitNode
from app.repositories.enum import UserRole
from app.repositories.permission_repository import PermissionRepository
from app.repositories.unit_node_repository import UnitNodeRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.schemas.mqtt.utils import get_topic_split
from app.schemas.pydantic.shared import MqttRead
from app.schemas.pydantic.unit import UnitCreate, UnitUpdate, UnitFilter, UnitRead, UnitMqttTokenAuth
from app.services.access_service import AccessService
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
def get(uuid: str, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.get(uuid).dict())


@router.get("/env/{uuid}", response_model=str)
def get_env(uuid: str, unit_service: UnitService = Depends()):
    return json.dumps(unit_service.get_env(uuid))


@router.get("/firmware/zip/{uuid}", response_model=bytes)
def get_firmware_zip(uuid: str, unit_service: UnitService = Depends()):
    zip_filepath = unit_service.get_unit_firmware_zip(uuid)

    def cleanup():
        os.remove(zip_filepath)

    print(zip_filepath)

    return FileResponse(zip_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tar/{uuid}", response_model=bytes)
def get_firmware_tar(uuid: str, unit_service: UnitService = Depends()):
    tar_filepath = unit_service.get_unit_firmware_tar(uuid)

    def cleanup():
        os.remove(tar_filepath)

    return FileResponse(tar_filepath, background=BackgroundTask(cleanup))


@router.get("/firmware/tgz/{uuid}", response_model=bytes)
def get_firmware_tgz(uuid: str, wbits: int = 9, level: int = 9, unit_service: UnitService = Depends()):
    tgz_filepath = unit_service.get_unit_firmware_tgz(uuid, wbits, level)

    def cleanup():
        os.remove(tgz_filepath)

    return FileResponse(tgz_filepath, background=BackgroundTask(cleanup))


# todo подлежит удалению
@router.post("/test/auth", response_model=str)
def get_token(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.generate_token(uuid)


@router.post("/auth", response_model=MqttRead, status_code=status.HTTP_200_OK)
def get_mqtt_auth(data: UnitMqttTokenAuth):
    db = next(get_session())

    access_service = AccessService(
        permission_repository=PermissionRepository(db),
        unit_repository=UnitRepository(db),
        user_repository=UserRepository(db),
        jwt_token=data.token,
    )
    access_service.access_check([UserRole.PEPEUNIT], is_unit_available=True)

    if isinstance(access_service.current_agent, Unit):
        backend_domain, destination, unit_uuid, topic_name, *_ = get_topic_split(data.topic)

        # todo проработать также остальные input_base подписки и output_base
        if destination == 'input_base' and topic_name == 'update':
            return MqttRead(result='allow')

        unit_node_repository = UnitNodeRepository(db)
        unit_node = unit_node_repository.get_by_topic(
            unit_uuid, UnitNode(topic_name=topic_name + '/pepeunit', type=destination.capitalize())
        )

        # todo на основании конфига есть два варианта поведения.
        # 1 грузим бекенд, запросами авторизации, но при этом всё ок нагрузкой на emqx
        # 2 грузим emqx любым лоадом, но разгружаем бекенд
        # сейчас используется 2й вариант
        if not unit_node:
            return MqttRead(result='deny')

        access_service.visibility_check(unit_node)

    db.close()

    return MqttRead(result='allow')


@router.patch("/{uuid}", response_model=UnitRead)
def update(uuid: str, data: UnitUpdate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.update(uuid, data).dict())


@router.patch("/env/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def set_env(uuid: str, env_json_str: str, unit_service: UnitService = Depends()):
    return unit_service.set_env(uuid, env_json_str)


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.delete(uuid)


@router.get("", response_model=list[UnitRead])
def get_units(filters: UnitFilter = Depends(UnitFilter), unit_service: UnitService = Depends()):
    return [UnitRead(**unit.dict()) for unit in unit_service.list(filters)]
