import enum

import strawberry


@strawberry.enum
class OrderByDate(str, enum.Enum):
    asc = 'asc'
    desc = 'desc'


@strawberry.enum
class VisibilityLevel(str, enum.Enum):
    """
    Visibility level for all entities
    """

    # for all
    PUBLIC = 'Public'
    # for all with auth at current Instance
    INTERNAL = 'Internal'
    # for all with Permission at current Instance, by default - only for creator and created Unit
    PRIVATE = 'Private'


@strawberry.enum
class UserRole(str, enum.Enum):
    """
    Role User in Pepeunit
    """

    BOT = 'Bot'  # special role for external users, not used in the database
    USER = 'User'
    ADMIN = 'Admin'
    PEPEUNIT = 'Pepeunit'  # Represents the Pepeunit instance, not used in the database


@strawberry.enum
class UserStatus(str, enum.Enum):
    """
    Status User in Pepeunit
    """

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'


@strawberry.enum
class AgentType(str, enum.Enum):
    """
    Agent type in the Pepeunit system
    """

    USER = 'User'
    UNIT = 'Unit'
    PEPEUNIT = 'Pepeunit'  # Represents the Pepeunit instance


@strawberry.enum
class UnitNodeTypeEnum(str, enum.Enum):
    """
    UnitNode types for database
    """

    OUTPUT = 'Output'
    INPUT = 'Input'


@strawberry.enum
class ReservedOutputBaseTopic(str, enum.Enum):
    """
    Booked output topics at Unit
    """

    STATE = 'state'


@strawberry.enum
class ReservedInputBaseTopic(str, enum.Enum):
    """
    Booked input topics at Unit
    """

    UPDATE = 'update'
    SCHEMA_UPDATE = 'schema_update'


@strawberry.enum
class DestinationTopicType(str, enum.Enum):
    """
    Allowed types of mqtt topic destinations
    """

    INPUT_BASE_TOPIC = 'input_base_topic'
    OUTPUT_BASE_TOPIC = 'output_base_topic'
    INPUT_TOPIC = 'input_topic'
    OUTPUT_TOPIC = 'output_topic'


@strawberry.enum
class GlobalPrefixTopic(str, enum.Enum):
    """
    Global topic prefixes
    """

    BACKEND_SUB_PREFIX = '/pepeunit'  # forwards the mqtt message to the Pepeunit instance


@strawberry.enum
class ReservedEnvVariableName(str, enum.Enum):
    """
    Reserved environment variable names in Unit
    """

    PEPEUNIT_URL = 'PEPEUNIT_URL'
    HTTP_TYPE = 'HTTP_TYPE'
    MQTT_URL = 'MQTT_URL'
    PEPEUNIT_TOKEN = 'PEPEUNIT_TOKEN'
    SYNC_ENCRYPT_KEY = 'SYNC_ENCRYPT_KEY'
    SECRET_KEY = 'SECRET_KEY'
    PING_INTERVAL = 'PING_INTERVAL'
    STATE_SEND_INTERVAL = 'STATE_SEND_INTERVAL'


@strawberry.enum
class CommandNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    START = 'start'
    HELP = 'help'
    INFO = 'info'
    VERIFICATION = 'verification'


@strawberry.enum
class PermissionEntities(str, enum.Enum):
    """
    Types of entities to which accesses are assigned
    """

    USER = 'User'
    UNIT = 'Unit'
    REPO = 'Repo'
    UNIT_NODE = 'UnitNode'
