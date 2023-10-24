import enum


class OrderByDate(str, enum.Enum):
    asc = 'asc'
    desc = 'desc'


class VisibilityLevel(enum.Enum):
    """Уровень видимости для сущностей"""

    PUBLIC = 'Public'
    INTERNAL = 'Internal'
    PRIVATE = 'Private'
