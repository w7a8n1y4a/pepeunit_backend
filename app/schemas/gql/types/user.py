import uuid as uuid_pkg
from datetime import datetime
from typing import Optional

import strawberry
from strawberry import field

from app.dto.enum import UserRole, UserStatus
from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class UserType(TypeInputMixin):
    uuid: uuid_pkg.UUID
    role: UserRole
    status: UserStatus
    login: str
    grafana_org_name: Optional[uuid_pkg.UUID] = None
    grafana_org_id: Optional[str] = None
    create_datetime: datetime

    hashed_password: strawberry.Private[object]
    cipher_dynamic_salt: strawberry.Private[object]
    telegram_chat_id: strawberry.Private[object]


@strawberry.type()
class UsersResultType(TypeInputMixin):
    count: int
    users: list[UserType] = field(default_factory=list)
