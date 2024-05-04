from fastapi import APIRouter, Depends

from app.schemas.pydantic.unit_node import UnitNodeRead, UnitNodeFilter, UnitNodeUpdate, UnitNodeSetState
from app.services.unit_node_service import UnitNodeService

router = APIRouter()


@router.get("/{uuid}", response_model=UnitNodeRead)
def get(uuid: str, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.get(uuid).dict())


@router.patch("/{uuid}", response_model=UnitNodeRead)
def update(uuid: str, data: UnitNodeUpdate, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.update(uuid, data).dict())


@router.patch("/set_state_input/{uuid}", response_model=UnitNodeRead)
def set_state_input(uuid: str, data: UnitNodeSetState, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.set_state_input(uuid, data).dict())


@router.get("", response_model=list[UnitNodeRead])
def get_unit_nodes(
    filters: UnitNodeFilter = Depends(UnitNodeFilter), unit_node_service: UnitNodeService = Depends()
):
    return [UnitNodeRead(**user.dict()) for user in unit_node_service.list(filters)]
