from fastapi import APIRouter, Depends
from fastapi_filter import FilterDepends
from sqlmodel import Session
from starlette.status import HTTP_200_OK

from app.core.auth.user_auth import user_token_required, Context
from app.core.db import get_session
from app.modules.user import crud
from app.modules.user.api_models import UserRead, UserCreate, UserAuth, UserFilter, AccessToken

router = APIRouter()


@router.post("", response_model=UserRead, status_code=HTTP_200_OK)
def create_user(data: UserCreate, db: Session = Depends(get_session)):
    return crud.create(data, db)


@router.post("/auth", response_model=AccessToken, status_code=HTTP_200_OK)
def generate_access_token(data: UserAuth, db: Session = Depends(get_session)):
    return crud.create_token(data, db)


@router.get("/{uuid}", response_model=UserRead, status_code=HTTP_200_OK)
def get_user(uuid: str, context: Context = Depends(user_token_required)):
    return crud.get(uuid, context.user, context.db)


@router.get("/current/", response_model=UserRead, status_code=HTTP_200_OK)
def get_current_user(context: Context = Depends(user_token_required)):
    return crud.get_current(context.user)


@router.get("", response_model=list[UserRead], status_code=HTTP_200_OK)
def get_users(filters: UserFilter = FilterDepends(UserFilter), context: Context = Depends(user_token_required)):
    return crud.get_all(filters, context.user, context.db)
