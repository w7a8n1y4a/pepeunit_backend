from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from sqlmodel import Session
from starlette.status import HTTP_200_OK

from app.core.auth.user_auth import token_required, Context
from app.core.db import get_session
from app.modules.user import crud
from app.modules.user.api_models import UserRead, UserCreate, UserFilter

router = APIRouter()


@router.post("", response_model=UserRead, status_code=HTTP_200_OK)
def create_user(data: UserCreate, db: Session = Depends(get_session)):
    return crud.create(data, db)


@router.get("/{uuid}", response_model=UserRead, status_code=HTTP_200_OK)
def get_user(uuid: str, context: Context = Depends(token_required)):
    return crud.get(uuid, context.user, context.db)


@router.get("", response_model=list[UserRead], status_code=HTTP_200_OK)
def get_users(filters: UserFilter = FilterDepends(UserFilter), context: Context = Depends(token_required)):
    return crud.get_all(filters, context.user, context.db)


@router.delete("", response_model=bool, status_code=HTTP_200_OK)
def delete_user(uuid: str, context: Context = Depends(token_required)):
    return crud.delete(uuid, context.user, context.db)
