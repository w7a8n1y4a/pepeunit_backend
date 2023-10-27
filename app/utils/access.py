from fastapi import HTTPException
from fastapi import status as http_status

from app.modules.user.enum import UserRole
from app.modules.user.sql_models import User


def access_check(user: User, roles: list[UserRole]):
    if user.role not in [role.value for role in roles]:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")


def creator_check(user: User, obj: any):
    if not user.uuid == obj.creator_uuid:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
