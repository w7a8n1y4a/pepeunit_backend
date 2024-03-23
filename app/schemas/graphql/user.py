import uuid as uuid_pkg
from datetime import datetime

import strawberry

from app.repositories.user_repository import UserStatus, UserRole


@strawberry.type(description="Author Schema")
class UserType:
    uuid: uuid_pkg.UUID
    role: UserRole
    status: UserStatus
    login: str
    email: str
    create_datetime: datetime

    hashed_password: strawberry.Private[object]
    cipher_dynamic_salt: strawberry.Private[object]
