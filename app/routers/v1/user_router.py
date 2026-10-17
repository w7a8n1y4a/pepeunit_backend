import uuid as uuid_pkg

from fastapi import APIRouter, Depends, Response, status

from app import runtime, settings
from app.configs.errors import FeatureFlagError
from app.configs.rest import ServiceFactory, get_user_service
from app.dto.enum import CookieName
from app.repositories.user_repository import UserFilter
from app.schemas.pydantic.user import (
    AccessToken,
    UserAuth,
    UserCreate,
    UserRead,
    UsersResult,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter()


def _set_grafana_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CookieName.PEPEUNIT_GRAFANA.value,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.pu_secure,
    )


def _clear_grafana_cookie(response: Response) -> None:
    response.delete_cookie(
        CookieName.PEPEUNIT_GRAFANA.value,
        httponly=True,
        samesite="lax",
        secure=settings.pu_secure,
    )


def _user_service_for_token(
    user_service: UserService, token: str
) -> UserService:
    data_pipe = user_service.data_pipe_repository.data_pipe_repository
    return ServiceFactory(
        db=user_service.user_repository.db,
        client=None if data_pipe is None else data_pipe.client,
        jwt_token=token,
    ).get_user_service()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: UserCreate, user_service: UserService = Depends(get_user_service)
):
    return UserRead(**user_service.create(data).dict())


@router.get("/{uuid}", response_model=UserRead)
def get(
    uuid: uuid_pkg.UUID, user_service: UserService = Depends(get_user_service)
):
    return UserRead(**user_service.get(uuid).dict())


@router.post("/auth", response_model=AccessToken)
def get_token(
    data: UserAuth,
    response: Response,
    user_service: UserService = Depends(get_user_service),
):
    token = user_service.get_token(data)
    if runtime.get().pu_ff_grafana_integration_enable:
        grafana_token = _user_service_for_token(
            user_service, token
        ).get_grafana_token()
        _set_grafana_cookie(response, grafana_token)
    return AccessToken(token=token)


@router.post("/grafana_cookie", status_code=status.HTTP_204_NO_CONTENT)
def set_grafana_cookie(
    response: Response,
    user_service: UserService = Depends(get_user_service),
):
    if not runtime.get().pu_ff_grafana_integration_enable:
        raise FeatureFlagError()

    _set_grafana_cookie(response, user_service.get_grafana_token())


@router.delete("/grafana_cookie", status_code=status.HTTP_204_NO_CONTENT)
def delete_grafana_cookie(response: Response) -> None:
    _clear_grafana_cookie(response)


@router.patch("/{uuid}", response_model=UserRead)
def update(
    data: UserUpdate, user_service: UserService = Depends(get_user_service)
):
    return UserRead(**user_service.update(data).dict())


@router.get("/generate_verification_link/", response_model=str)
async def get_verification(
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.generate_verification_link()


@router.patch("/grant_admin/{uuid}", response_model=UserRead)
def grant_admin(
    uuid: uuid_pkg.UUID, user_service: UserService = Depends(get_user_service)
):
    return UserRead(**user_service.grant_admin(uuid).dict())


@router.patch("/revoke_admin/{uuid}", response_model=UserRead)
def revoke_admin(
    uuid: uuid_pkg.UUID, user_service: UserService = Depends(get_user_service)
):
    return UserRead(**user_service.revoke_admin(uuid).dict())


@router.patch("/block/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def block(
    uuid: uuid_pkg.UUID, user_service: UserService = Depends(get_user_service)
):
    return user_service.block(uuid)


@router.patch("/unblock/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def unblock(
    uuid: uuid_pkg.UUID, user_service: UserService = Depends(get_user_service)
):
    return user_service.unblock(uuid)


@router.get("", response_model=UsersResult)
def get_users(
    filters: UserFilter = Depends(UserFilter),
    user_service: UserService = Depends(get_user_service),
):
    count, users = user_service.list(filters)
    return UsersResult(
        count=count, users=[UserRead(**user.dict()) for user in users]
    )
