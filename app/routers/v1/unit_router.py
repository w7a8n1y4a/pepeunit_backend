from fastapi import APIRouter, Depends, status
from fastapi_filter import FilterDepends

from app.schemas.pydantic.unit import UnitCreate, UnitUpdate, UnitFilter, UnitRead
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


@router.patch("/{uuid}", response_model=UnitRead)
def update(uuid: str, data: UnitUpdate, unit_service: UnitService = Depends()):
    return UnitRead(**unit_service.update(uuid, data).dict())


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(uuid: str, unit_service: UnitService = Depends()):
    return unit_service.delete(uuid)


@router.get("", response_model=list[UnitRead])
def get_units(filters: UnitFilter = FilterDepends(UnitFilter), unit_service: UnitService = Depends()):
    return [UnitRead(**unit.dict()) for unit in unit_service.list(filters)]
