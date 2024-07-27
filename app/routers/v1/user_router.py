from fastapi import APIRouter, Depends, status

from app.repositories.user_repository import UserFilter
from app.schemas.pydantic.user import UserRead, UserCreate, UserUpdate, AccessToken, UserAuth
from app.services.user_service import UserService
from app.services.validators import is_valid_uuid

router = APIRouter()


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create(data: UserCreate, user_service: UserService = Depends()):
    return UserRead(**user_service.create(data).dict())


@router.get("/{uuid}", response_model=UserRead)
def get(uuid: str, user_service: UserService = Depends()):
    return UserRead(**user_service.get(is_valid_uuid(uuid)).dict())


@router.post("/auth", response_model=AccessToken)
def get_token(data: UserAuth, user_service: UserService = Depends()):
    return AccessToken(token=user_service.get_token(data))


@router.patch("/{uuid}", response_model=UserRead)
def update(uuid: str, data: UserUpdate, user_service: UserService = Depends()):
    return UserRead(**user_service.update(is_valid_uuid(uuid), data).dict())


@router.get("/generate_verification_code/", response_model=str)
async def get_verification(user_service: UserService = Depends()):
    code = await user_service.generate_verification_code()
    return code


@router.patch("/block/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def block(uuid: str, user_service: UserService = Depends()):
    return user_service.block(is_valid_uuid(uuid))


@router.patch("/unblock/{uuid}", status_code=status.HTTP_204_NO_CONTENT)
def unblock(uuid: str, user_service: UserService = Depends()):
    return user_service.unblock(is_valid_uuid(uuid))


@router.get("", response_model=list[UserRead])
def get_users(filters: UserFilter = Depends(UserFilter), user_service: UserService = Depends()):
    return [UserRead(**user.dict()) for user in user_service.list(filters)]
