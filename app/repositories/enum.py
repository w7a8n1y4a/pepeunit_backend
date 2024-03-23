import enum

import strawberry


@strawberry.enum
class OrderByDate(str, enum.Enum):
    asc = 'asc'
    desc = 'desc'


@strawberry.enum
class VisibilityLevel(str, enum.Enum):
    """Уровень видимости для сущностей"""

    # всем кто зашёл на узел
    PUBLIC = 'Public'
    # всем кто авторизовался
    INTERNAL = 'Internal'
    # всем кому предоставлен доступ создателем
    PRIVATE = 'Private'


@strawberry.enum
class UserRole(enum.Enum):
    """Роль пользователя"""

    USER = 'User'
    ADMIN = 'Admin'


@strawberry.enum
class UserStatus(enum.Enum):
    """Статус пользователя"""

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'