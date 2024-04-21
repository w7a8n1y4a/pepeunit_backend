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
class UserRole(str, enum.Enum):
    """Роль пользователя"""

    # специальная роль для внешних пользователей
    BOT = 'Bot'
    USER = 'User'
    ADMIN = 'Admin'


@strawberry.enum
class UserStatus(str, enum.Enum):
    """Статус пользователя"""

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'


class AgentType(str, enum.Enum):
    USER = 'User'
    UNIT = 'Unit'


class UnitNodeType(str, enum.Enum):
    OUTPUT = 'Output'
    INPUT = 'Input'


class OutputBaseTopic(str, enum.Enum):
    STATE = 'state'
