from fastapi import APIRouter, Depends, status
from fastapi_filter import FilterDepends

from app.repositories.user_repository import UserFilter
from app.schemas.pydantic.user import UserRead, UserCreate, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    user: UserCreate,
    user_service: UserService = Depends()
):
    return UserRead(**user_service.create(user).dict())


@router.get("/{uuid}", response_model=UserRead)
def get(
    uuid: str,
    user_service: UserService = Depends()
):
    return UserRead(**user_service.get(uuid).dict())


@router.patch("/{id}", response_model=UserRead)
def update(
    uuid: str,
    user: UserUpdate,
    user_service: UserService = Depends()
):
    return UserRead(**user_service.update(uuid, user).dict())


@router.delete(
    "/{uuid}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete(
    uuid: str,
    user_service: UserService = Depends()
):
    return user_service.delete(uuid)


@router.get("", response_model=list[UserRead])
def get_users(
    filters: UserFilter = FilterDepends(UserFilter),
    user_service: UserService = Depends()
):
    return [
        UserRead(**user.dict()) for user in user_service.list(filters)
    ]
