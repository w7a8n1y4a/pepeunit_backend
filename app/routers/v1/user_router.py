import uuid as uuid_pkg

from fastapi import APIRouter, Depends, status

from app.repositories.user_repository import UserFilter
from app.schemas.pydantic.user import AccessToken, UserAuth, UserCreate, UserRead, UsersResult, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: UserCreate, user_service: UserService = Depends()):
    return UserRead(**user_service.create(data).dict())


@router.get("/{uuid}", response_model=UserRead)
def get(uuid: uuid_pkg.UUID, user_service: UserService = Depends()):
    return UserRead(**user_service.get(uuid).dict())


@router.post("/auth", response_model=AccessToken)
def get_token(data: UserAuth, user_service: UserService = Depends()):
    return AccessToken(token=user_service.get_token(data))


@router.patch("/{uuid}", response_model=UserRead)
def update(data: UserUpdate, user_service: UserService = Depends()):
    return UserRead(**user_service.update(data).dict())


@router.get("/generate_verification_link/", response_model=str)
async def get_verification(user_service: UserService = Depends()):
    return await user_service.generate_verification_link()


@router.patch("/block/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def block(uuid: uuid_pkg.UUID, user_service: UserService = Depends()):
    return user_service.block(uuid)


@router.patch("/unblock/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def unblock(uuid: uuid_pkg.UUID, user_service: UserService = Depends()):
    return user_service.unblock(uuid)


@router.get("", response_model=UsersResult)
def get_users(filters: UserFilter = Depends(UserFilter), user_service: UserService = Depends()):
    print(user_service.access_service.auth.jwt_token)
    count, users = user_service.list(filters)
    return UsersResult(count=count, users=[UserRead(**user.dict()) for user in users])
