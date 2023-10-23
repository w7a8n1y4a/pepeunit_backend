from fastapi import HTTPException
from fastapi import status as http_status

from app.modules.user.enum import UserRole
from app.modules.user.sql_models import User


def access_check(user: User):
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=f"No access")
