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
    GRAFANA = 'Grafana'
    GRAFANA_UNIT_NODE = 'GrafanaUnitNode'


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
    REGISTRY = 'registry'
    REPO = 'repo'
    UNIT = 'unit'
    INFO = 'info'
    VERIFICATION = 'verification'


@strawberry.enum
class EntityNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    REGISTRY = 'Registry'
    REPO = 'Repo'
    UNIT = 'Unit'
    UNIT_NODE = 'UnitNode'
    UNIT_LOG = 'UnitLog'


@strawberry.enum
class DecreesNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    RELATED_UNIT = 'RelatedUnit'
    LOCAL_UPDATE = 'LocalUpdate'
    GET_ENV = 'GetEnv'
    TAR = 'Tar'
    TGZ = 'Tgz'
    ZIP = 'Zip'


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


@strawberry.enum
class DataPipeStatus(str, enum.Enum):
    """
    Types of state data pipeline
    """

    ACTIVE = 'Active'
    INACTIVE = 'Inactive'
    ERROR = 'Error'


@strawberry.enum
class DataPipeStage(str, enum.Enum):
    """
    Stages data pipeline
    """

    ACTIVE_PERIOD = 'ActivePeriod'
    FILTERS = 'Filters'
    TRANSFORMATIONS = 'Transformations'
    PROCESSING_POLICY = 'ProcessingPolicy'


@strawberry.enum
class ActivePeriodType(str, enum.Enum):
    PERMANENT = "Permanent"
    FROM_DATE = "FromDate"
    TO_DATE = "ToDate"
    DATE_RANGE = "DateRange"


@strawberry.enum
class TypeInputValue(str, enum.Enum):
    TEXT = "Text"
    NUMBER = "Number"


@strawberry.enum
class FilterTypeValueFiltering(str, enum.Enum):
    WHITELIST = "WhiteList"
    BLACKLIST = "BlackList"


@strawberry.enum
class FilterTypeValueThreshold(str, enum.Enum):
    MIN = "Min"
    MAX = "Max"
    RANGE = "Range"


@strawberry.enum
class ProcessingPolicyType(str, enum.Enum):
    LAST_VALUE = "LastValue"
    N_RECORDS = "NRecords"
    TIME_WINDOW = "TimeWindow"
    AGGREGATION = "Aggregation"


@strawberry.enum
class AggregationFunctions(str, enum.Enum):
    AVG = "Avg"
    MIN = "Min"
    MAX = "Max"
    SUM = "Sum"


@strawberry.enum
class DatasourceFormat(str, enum.Enum):
    TIMESERIES = "timeseries"
    TABLE = "table"


@strawberry.enum
class RepositoryRegistryStatus(str, enum.Enum):
    """
    Types of state RepositoryRegistry
    """

    UPDATED = 'Updated'
    PROCESSING = 'Processing'
    ERROR = 'Error'


@strawberry.enum
class CredentialStatus(str, enum.Enum):
    """
    Types of state CredentialStatus
    """

    VALID = 'Valid'
    NOT_VERIFIED = 'NotVerified'
    ERROR = 'Error'


@strawberry.enum
class RepositoryRegistryType(str, enum.Enum):
    """
    Types of log levels
    """

    PRIVATE = 'Private'
    PUBLIC = 'Public'


@strawberry.enum
class GrafanaUserRole(str, enum.Enum):
    """
    Role User for Grafana
    """

    VIEWER = 'Viewer'
    EDITOR = 'Editor'
    ADMIN = 'Admin'


@strawberry.enum
class CookieName(str, enum.Enum):
    """
    All Cookies names
    """

    PEPEUNIT_GRAFANA = 'PepeunitGrafana'


@strawberry.enum
class DashboardPanelType(str, enum.Enum):
    """
    All dashboard panel types
    """

    HOURLY_HEATMAP = 'marcusolsson-hourly-heatmap-panel'
