import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.configs.rest import get_unit_group_service
from app.schemas.pydantic.unit import UnitRead, UnitsResult
from app.schemas.pydantic.unit_group import (
    UnitGroupCreate,
    UnitGroupFilter,
    UnitGroupMemberFilter,
    UnitGroupRead,
    UnitGroupsResult,
    UnitGroupUpdate,
)
from app.services.unit_group_service import UnitGroupService

router = APIRouter()


@router.post(
    "",
    response_model=UnitGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: UnitGroupCreate,
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    return UnitGroupRead(**unit_group_service.create(data).dict())


@router.get("/{uuid}", response_model=UnitGroupRead)
def get(
    uuid: uuid_pkg.UUID,
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    return UnitGroupRead(**unit_group_service.get(uuid).dict())


@router.get("/{uuid}/units", response_model=UnitsResult)
def get_group_units(
    uuid: uuid_pkg.UUID,
    filters: UnitGroupMemberFilter = Depends(UnitGroupMemberFilter),
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    count, units = unit_group_service.list_units(uuid, filters)
    return UnitsResult(
        count=count, units=[UnitRead(**unit.to_dict()) for unit in units]
    )


@router.post(
    "/{uuid}/units/{unit_uuid}", status_code=status.HTTP_204_NO_CONTENT
)
def link_unit(
    uuid: uuid_pkg.UUID,
    unit_uuid: uuid_pkg.UUID,
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    return unit_group_service.link_unit(uuid, unit_uuid)


@router.delete(
    "/{uuid}/units/{unit_uuid}", status_code=status.HTTP_204_NO_CONTENT
)
def unlink_unit(
    uuid: uuid_pkg.UUID,
    unit_uuid: uuid_pkg.UUID,
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    return unit_group_service.unlink_unit(uuid, unit_uuid)


@router.patch("/{uuid}", response_model=UnitGroupRead)
def update(
    uuid: uuid_pkg.UUID,
    data: UnitGroupUpdate,
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    return UnitGroupRead(**unit_group_service.update(uuid, data).dict())


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    uuid: uuid_pkg.UUID,
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    return unit_group_service.delete(uuid)


@router.get("", response_model=UnitGroupsResult)
def get_unit_groups(
    filters: UnitGroupFilter = Depends(UnitGroupFilter),
    unit_group_service: UnitGroupService = Depends(get_unit_group_service),
):
    count, groups = unit_group_service.list(filters)
    return UnitGroupsResult(
        count=count,
        unit_groups=[UnitGroupRead(**group.dict()) for group in groups],
    )
