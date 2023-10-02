from fastapi import APIRouter
from starlette.status import HTTP_200_OK

from app.modules.devices import crud
from app.modules.devices.models import UnitRead

router = APIRouter()


@router.post("", response_model=UnitRead, status_code=HTTP_200_OK)
def create(name: str, repository_link: str):
    return crud.create(name, repository_link)


@router.get("", response_model=list[UnitRead], status_code=HTTP_200_OK)
def get_files():
    return crud.get_all()
