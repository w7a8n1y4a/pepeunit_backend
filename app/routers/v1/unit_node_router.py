import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.schemas.pydantic.unit import UnitRead
from app.schemas.pydantic.unit_node import (
    UnitNodeEdgeCreate,
    UnitNodeEdgeOutputFilter,
    UnitNodeEdgeRead,
    UnitNodeFilter,
    UnitNodeOutputRead,
    UnitNodeRead,
    UnitNodeSetState,
    UnitNodesOutputsResult,
    UnitNodeUpdate,
)
from app.services.unit_node_service import UnitNodeService

router = APIRouter()


@router.get("/{uuid}", response_model=UnitNodeRead)
def get(uuid: uuid_pkg.UUID, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.get(uuid).dict())


@router.patch("/{uuid}", response_model=UnitNodeRead)
def update(uuid: uuid_pkg.UUID, data: UnitNodeUpdate, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.update(uuid, data).dict())


@router.patch("/set_state_input/{uuid}", response_model=UnitNodeRead)
def set_state_input(uuid: uuid_pkg.UUID, data: UnitNodeSetState, unit_node_service: UnitNodeService = Depends()):
    return UnitNodeRead(**unit_node_service.set_state_input(uuid, data).dict())


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
def delete_unit_node_edge(
    input_uuid: uuid_pkg.UUID, output_uuid: uuid_pkg.UUID, unit_node_service: UnitNodeService = Depends()
):
    return unit_node_service.delete_node_edge(input_uuid, output_uuid)


@router.get("/get_output_unit_nodes/", response_model=UnitNodesOutputsResult)
def get_output_unit_nodes(
    filters: UnitNodeEdgeOutputFilter = Depends(UnitNodeEdgeOutputFilter),
    unit_node_service: UnitNodeService = Depends(),
):
    count, unit_nodes = unit_node_service.get_output_unit_nodes(filters)
    return UnitNodesOutputsResult(
        count=count,
        unit_nodes_output=[
            UnitNodeOutputRead(
                unit=UnitRead(**item[0].dict()), unit_output_nodes=[UnitNodeRead(**node) for node in item[1]]
            )
            for item in unit_nodes
        ],
    )
