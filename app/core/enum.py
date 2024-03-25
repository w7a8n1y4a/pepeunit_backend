import enum


class OrderByDate(str, enum.Enum):
    asc = 'asc'
    desc = 'desc'


class VisibilityLevel(str, enum.Enum):
    """Уровень видимости для сущностей"""

    # всем кто зашёл на узел
    PUBLIC = 'Public'
    # всем кто авторизовался
    INTERNAL = 'Internal'
    # всем кому предоставлен доступ создателем
    PRIVATE = 'Private'
