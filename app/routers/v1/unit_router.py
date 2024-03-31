from fastapi import APIRouter, Depends, status
from fastapi_filter import FilterDepends
from pydantic import BaseModel

from app.configs.db import get_session
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
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


# todo подлежит удалению
@router.post("/test/auth", response_model=str)
def get_token(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.generate_token(uuid)


@router.post("/auth", response_model=bool, status_code=status.HTTP_200_OK)
def get_mqtt_auth(data: UnitMqttTokenAuth):

    db = next(get_session())

    # todo добавить проверку доступных топиков
    access_service = AccessService(
        user_repository=UserRepository(db=db),
        unit_repository=UnitRepository(db=db),
        jwt_token=data.token
    )

    db.close()

    print(data.topic)

    return True


@router.patch("/{uuid}", response_model=UnitRead)
def update(uuid: str, data: UnitUpdate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.update(uuid, data).dict())


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.delete(uuid)


@router.get("", response_model=list[UnitRead])
def get_units(filters: UnitFilter = FilterDepends(UnitFilter), unit_service: UnitService = Depends()):
    return [UnitRead(**unit.dict()) for unit in unit_service.list(filters)]
