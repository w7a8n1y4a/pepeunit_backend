import uuid as uuid_pkg

from fastapi import APIRouter, Depends, UploadFile, status

from app.configs.rest import get_unit_node_service
from app.schemas.pydantic.shared import UnitNodeRead, UnitNodesResult
from app.schemas.pydantic.unit_node import (
    UnitNodeEdgeCreate,
    UnitNodeEdgeRead,
    UnitNodeFilter,
    UnitNodeSetState,
    UnitNodeUpdate,
)
from app.services.unit_node_service import UnitNodeService

router = APIRouter()


@router.get("/{uuid}", response_model=UnitNodeRead)
def get(uuid: uuid_pkg.UUID, unit_node_service: UnitNodeService = Depends(get_unit_node_service)):
    return UnitNodeRead(**unit_node_service.get(uuid).dict())


@router.patch("/{uuid}", response_model=UnitNodeRead)
def update(
    uuid: uuid_pkg.UUID, data: UnitNodeUpdate, unit_node_service: UnitNodeService = Depends(get_unit_node_service)
):
    return UnitNodeRead(**unit_node_service.update(uuid, data).dict())


@router.patch("/set_state_input/{uuid}", response_model=UnitNodeRead)
def set_state_input(
    uuid: uuid_pkg.UUID, data: UnitNodeSetState, unit_node_service: UnitNodeService = Depends(get_unit_node_service)
):
    return UnitNodeRead(**unit_node_service.set_state_input(uuid, data).dict())


@router.post("/check_data_pipe_config/")
async def check_data_pipe_config(data: UploadFile, unit_node_service: UnitNodeService = Depends(get_unit_node_service)):
    await unit_node_service.check_data_pipe_config(data)


@router.get("", response_model=UnitNodesResult)
def get_unit_nodes(
    filters: UnitNodeFilter = Depends(UnitNodeFilter),
    unit_node_service: UnitNodeService = Depends(get_unit_node_service),
):
    count, unit_nodes = unit_node_service.list(filters)
    return UnitNodesResult(count=count, unit_nodes=[UnitNodeRead(**unit_node.dict()) for unit_node in unit_nodes])


@router.post(
    "/create_unit_node_edge",
    response_model=UnitNodeEdgeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_unit_node_edge(
    data: UnitNodeEdgeCreate, unit_node_service: UnitNodeService = Depends(get_unit_node_service)
):
    return UnitNodeEdgeRead(**unit_node_service.create_node_edge(data).dict())
