from fastapi import APIRouter, Depends, status

from app.schemas.pydantic.unit_node import (
    UnitNodeRead,
    UnitNodeFilter,
    UnitNodeUpdate,
    UnitNodeSetState,
    UnitNodeEdgeRead,
    UnitNodeEdgeCreate,
)
from app.services.unit_node_service import UnitNodeService
from app.services.validators import is_valid_uuid

router = APIRouter()


@router.get("/{uuid}", response_model=UnitNodeRead)
def get(uuid: str, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.get(is_valid_uuid(uuid)).dict())


@router.patch("/{uuid}", response_model=UnitNodeRead)
def update(uuid: str, data: UnitNodeUpdate, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.update(is_valid_uuid(uuid), data).dict())


@router.patch("/set_state_input/{uuid}", response_model=UnitNodeRead)
def set_state_input(uuid: str, data: UnitNodeSetState, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.set_state_input(is_valid_uuid(uuid), data).dict())


@router.get("", response_model=list[UnitNodeRead])
def get_unit_nodes(filters: UnitNodeFilter = Depends(UnitNodeFilter), unit_node_service: UnitNodeService = Depends()):
    return [UnitNodeRead(**user.dict()) for user in unit_node_service.list(filters)]


@router.post(
    "/create_unit_node_edge",
    response_model=UnitNodeEdgeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_unit_node_edge(data: UnitNodeEdgeCreate, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeEdgeRead(**unit_node_service.create_node_edge(data).dict())


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit_node_edge(uuid: str, unit_node_service: UnitNodeService = Depends()):
    return unit_node_service.delete_node_edge(is_valid_uuid(uuid))
