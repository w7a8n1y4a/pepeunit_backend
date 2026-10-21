import os
import uuid as uuid_pkg

from fastapi import APIRouter, Depends, UploadFile, status
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from app.configs.rest import get_unit_io_service
from app.schemas.pydantic.shared import UnitIORead, UnitIOsResult
from app.schemas.pydantic.unit_io import (
    DataPipeFilter,
    DataPipeValidationErrorRead,
    LinkCreate,
    LinkRead,
    PipeDataResult,
    UnitIOFilter,
    UnitIOSetState,
    UnitIOUpdate,
)
from app.services.unit_io_service import UnitIOService

router = APIRouter()


@router.get("/{uuid}", response_model=UnitIORead)
def get(
    uuid: uuid_pkg.UUID,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return UnitIORead(**unit_io_service.get(uuid).dict())


@router.patch("/{uuid}", response_model=UnitIORead)
async def update(
    uuid: uuid_pkg.UUID,
    data: UnitIOUpdate,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return UnitIORead(**(await unit_io_service.update(uuid, data)).dict())


@router.patch("/set_state_input/{uuid}", response_model=UnitIORead)
def set_state_input(
    uuid: uuid_pkg.UUID,
    data: UnitIOSetState,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return UnitIORead(**unit_io_service.set_state_input(uuid, data).dict())


@router.post(
    "/check_data_pipe_config", response_model=list[DataPipeValidationErrorRead]
)
async def check_data_pipe_config(
    data: UploadFile,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return await unit_io_service.check_data_pipe_config(data)


@router.post("/set_data_pipe_config", status_code=status.HTTP_204_NO_CONTENT)
async def set_data_pipe_config(
    uuid: uuid_pkg.UUID,
    data: UploadFile,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return await unit_io_service.set_data_pipe_config(uuid, data)


@router.get("/get_data_pipe_config/{uuid}", response_model=bytes)
def get_data_pipe_config(
    uuid: uuid_pkg.UUID,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    yml_filepath = unit_io_service.get_data_pipe_config(uuid)

    def cleanup():
        os.remove(yml_filepath)

    return FileResponse(yml_filepath, background=BackgroundTask(cleanup))


@router.get("/get_data_pipe_data/", response_model=PipeDataResult)
def get_data_pipe_data(
    filters: DataPipeFilter = Depends(DataPipeFilter),
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    count, pipe_data = unit_io_service.get_data_pipe_data(filters)
    return PipeDataResult(count=count, pipe_data=pipe_data)


@router.get("/get_data_pipe_data_csv/{uuid}", response_model=bytes)
def get_data_pipe_data_csv(
    uuid: uuid_pkg.UUID,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    csv_filepath = unit_io_service.get_data_pipe_data_csv(uuid)

    def cleanup():
        os.remove(csv_filepath)

    return FileResponse(csv_filepath, background=BackgroundTask(cleanup))


@router.post("/set_data_pipe_data_csv", status_code=status.HTTP_204_NO_CONTENT)
async def set_data_pipe_data_csv(
    uuid: uuid_pkg.UUID,
    data: UploadFile,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return await unit_io_service.set_data_pipe_data_csv(uuid, data)


@router.delete(
    "/delete_data_pipe_data/{uuid}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_data_pipe_data(
    uuid: uuid_pkg.UUID,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return unit_io_service.delete_data_pipe_data(uuid)


@router.get("", response_model=UnitIOsResult)
def get_unit_ios(
    filters: UnitIOFilter = Depends(UnitIOFilter),
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    count, unit_ios = unit_io_service.list(filters)
    return UnitIOsResult(
        count=count,
        unit_ios=[UnitIORead(**unit_io.dict()) for unit_io in unit_ios],
    )


@router.post(
    "/create_link",
    response_model=LinkRead,
    status_code=status.HTTP_201_CREATED,
)
def create_link(
    data: LinkCreate,
    unit_io_service: UnitIOService = Depends(get_unit_io_service),
):
    return LinkRead(**unit_io_service.create_link(data).dict())
