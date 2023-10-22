import enum


class UserRole(enum.Enum):
    """ Роль пользователя """

    USER = 'User'
    ADMIN = 'Admin'


class UserStatus(enum.Enum):
    """ Статус пользователя """

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'
