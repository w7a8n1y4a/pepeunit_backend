from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from starlette.status import HTTP_200_OK

from app.core.auth.user_auth import user_token_required, Context
from app.modules.unit import crud
from app.modules.unit.api_models import UnitRead, UnitUpdate, UnitFilter, UnitCreate

router = APIRouter()


@router.post("", response_model=UnitRead, status_code=HTTP_200_OK)
def create_unit(data: UnitCreate, context: Context = Depends(user_token_required)):
    return crud.create(data, context.user, context.db)


@router.put("/{uuid}", response_model=UnitRead, status_code=HTTP_200_OK)
def update_unit(uuid: str, data: UnitUpdate, context: Context = Depends(user_token_required)):
    return crud.update(uuid, data, context.user, context.db)


@router.get("/{uuid}", response_model=UnitRead, status_code=HTTP_200_OK)
def get_unit(uuid: str, context: Context = Depends(user_token_required)):
    return crud.get(uuid, context.user, context.db)


@router.get("/program/{uuid}", response_model=str, status_code=HTTP_200_OK)
def get_unit_program(uuid: str, context: Context = Depends(user_token_required)):
    return crud.get_program(uuid, context.user, context.db)


@router.get("", response_model=list[UnitRead], status_code=HTTP_200_OK)
def get_unis(filters: UnitFilter = FilterDepends(UnitFilter), context: Context = Depends(user_token_required)):
    return crud.gets(filters, context.user, context.db)
