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
    PEPEUNIT = 'Pepeunit'


@strawberry.enum
class UserStatus(str, enum.Enum):
    """Статус пользователя"""

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'


@strawberry.enum
class AgentType(str, enum.Enum):
    USER = 'User'
    UNIT = 'Unit'
    PEPEUNIT = 'Pepeunit'


@strawberry.enum
class UnitNodeTypeEnum(str, enum.Enum):
    OUTPUT = 'Output'
    INPUT = 'Input'


@strawberry.enum
class ReservedOutputBaseTopic(str, enum.Enum):
    """Забронированные топики вывода у Unit"""

    STATE = 'state'


@strawberry.enum
class SchemaStructName(str, enum.Enum):
    """Разрешённые назначения топиков схемы у Unit"""

    INPUT_BASE_TOPIC = 'input_base_topic'
    OUTPUT_BASE_TOPIC = 'output_base_topic'
    INPUT_TOPIC = 'input_topic'
    OUTPUT_TOPIC = 'output_topic'


@strawberry.enum
class ReservedEnvVariableName(str, enum.Enum):
    """Зарезервированные имена переменных окружения у Unit"""

    PEPEUNIT_URL = 'PEPEUNIT_URL'
    MQTT_URL = 'MQTT_URL'
    PEPEUNIT_TOKEN = 'PEPEUNIT_TOKEN'
    SYNC_ENCRYPT_KEY = 'SYNC_ENCRYPT_KEY'
    SECRET_KEY = 'SECRET_KEY'
    PING_INTERVAL = 'PING_INTERVAL'
    STATE_SEND_INTERVAL = 'STATE_SEND_INTERVAL'


class CommandNames(str, enum.Enum):
    """Команды поддерживаемые ботом"""

    START = 'start'
    HELP = 'help'
    INFO = 'info'
    VERIFICATION = 'verification'


class PermissionEntities(str, enum.Enum):

    USER = 'User'
    UNIT = 'Unit'
    REPO = 'Repo'
    UNIT_NODE = 'UnitNode'
