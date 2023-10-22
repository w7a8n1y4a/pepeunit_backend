import enum


class VisibilityLevel(enum.Enum):
    """ Уровень видимости для сущностей """

    PUBLIC = 'Public'
    INTERNAL = 'Internal'
    PRIVATE = 'Private'
