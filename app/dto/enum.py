import enum

import strawberry


@strawberry.enum
class OrderByDate(str, enum.Enum):
    asc = 'asc'
    desc = 'desc'


@strawberry.enum
class OrderByText(str, enum.Enum):
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

    USER = 'User'
    ADMIN = 'Admin'


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

    BOT = 'Bot'
    USER = 'User'
    UNIT = 'Unit'
    BACKEND = 'Backend'


@strawberry.enum
class AgentStatus(str, enum.Enum):
    """
    Status User in Pepeunit
    """

    UNVERIFIED = 'Unverified'
    VERIFIED = 'Verified'
    BLOCKED = 'Blocked'


@strawberry.enum
class OwnershipType(str, enum.Enum):
    """
    Ownership rules type
    """

    CREATOR = 'Creator'
    UNIT = 'Unit'
    UNIT_TO_INPUT_NODE = 'UnitToInputNode'


@strawberry.enum
class UnitNodeTypeEnum(str, enum.Enum):
    """
    UnitNode types for database
    """

    OUTPUT = 'Output'
    INPUT = 'Input'


@strawberry.enum
class UnitFirmwareUpdateStatus(str, enum.Enum):
    """
    Unit update status
    """

    REQUEST_SENT = 'RequestSent'
    ERROR = 'Error'
    SUCCESS = 'Success'


@strawberry.enum
class ReservedOutputBaseTopic(str, enum.Enum):
    """
    Booked output topics at Unit
    """

    STATE = 'state'
    LOG = 'log'


@strawberry.enum
class BackendTopicCommand(str, enum.Enum):
    """
    Booked input topics at Unit
    """

    UPDATE = 'Update'
    ENV_UPDATE = 'EnvUpdate'
    SCHEMA_UPDATE = 'SchemaUpdate'
    LOG_SYNC = 'LogSync'


@strawberry.enum
class ReservedInputBaseTopic(str, enum.Enum):
    """
    Booked input topics at Unit
    """

    UPDATE = 'update'
    ENV_UPDATE = 'env_update'
    SCHEMA_UPDATE = 'schema_update'
    LOG_SYNC = 'log_sync'


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
class StaticRepoFileName(str, enum.Enum):
    """
    Static files
    """

    SCHEMA_EXAMPLE = 'schema_example.json'
    SCHEMA = 'schema.json'
    ENV_EXAMPLE = 'env_example.json'
    ENV = 'env.json'


@strawberry.enum
class ReservedStateKey(str, enum.Enum):
    """
    Reserved state Unit keys
    """

    IFCONFIG = 'ifconfig'
    MILLIS = 'millis'
    MEM_FREE = 'mem_free'
    MEM_ALLOC = 'mem_alloc'
    FREQ = 'freq'
    STATVFS = 'statvfs'
    COMMIT_VERSION = 'commit_version'


@strawberry.enum
class ReservedEnvVariableName(str, enum.Enum):
    """
    Reserved environment variable names in Unit
    """

    PEPEUNIT_URL = 'PEPEUNIT_URL'
    HTTP_TYPE = 'HTTP_TYPE'
    PEPEUNIT_APP_PREFIX = 'PEPEUNIT_APP_PREFIX'
    PEPEUNIT_API_ACTUAL_PREFIX = 'PEPEUNIT_API_ACTUAL_PREFIX'
    MQTT_URL = 'MQTT_URL'
    MQTT_PORT = 'MQTT_PORT'
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
    REPO = 'repo'
    UNIT = 'unit'
    INFO = 'info'
    VERIFICATION = 'verification'


@strawberry.enum
class EntityNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    REPO = 'Repo'
    UNIT = 'Unit'
    UNIT_LOG = 'UnitLog'


@strawberry.enum
class DecreesNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    RELATED_UNIT = 'RelatedUnit'
    LOCAL_UPDATE = 'LocalUpdate'
    GET_ENV = 'GetEnv'


@strawberry.enum
class PermissionEntities(str, enum.Enum):
    """
    Types of entities to which accesses are assigned
    """

    USER = 'User'
    UNIT = 'Unit'
    REPO = 'Repo'
    UNIT_NODE = 'UnitNode'


@strawberry.enum
class GitPlatform(str, enum.Enum):
    """
    Types git platforms
    """

    GITLAB = 'Gitlab'
    GITHUB = 'Github'


@strawberry.enum
class LogLevel(str, enum.Enum):
    """
    Types of log levels
    """

    DEBUG = 'Debug'
    INFO = 'Info'
    WARNING = 'Warning'
    ERROR = 'Error'
    CRITICAL = 'Critical'
