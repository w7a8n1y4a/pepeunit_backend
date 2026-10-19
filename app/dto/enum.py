import enum


class OrderByDate(str, enum.Enum):
    asc = "asc"
    desc = "desc"


class OrderByText(str, enum.Enum):
    asc = "asc"
    desc = "desc"


class VisibilityLevel(str, enum.Enum):
    """
    Visibility level for all entities
    """

    # for all
    PUBLIC = "Public"
    # for all with auth at current Instance
    INTERNAL = "Internal"
    # for all with Permission at current Instance, by default - only for creator and created Unit
    PRIVATE = "Private"


class UserRole(str, enum.Enum):
    """
    Role User in Pepeunit
    """

    USER = "User"
    ADMIN = "Admin"
    OWNER = "Owner"


class UserStatus(str, enum.Enum):
    """
    Status User in Pepeunit
    """

    ACTIVE = "Active"
    BLOCKED = "Blocked"


class AgentType(str, enum.Enum):
    """
    Agent type in the Pepeunit system
    """

    BOT = "Bot"
    USER = "User"
    UNIT = "Unit"
    BACKEND = "Backend"
    GRAFANA = "Grafana"
    GRAFANA_UNIT_IO = "GrafanaUnitIO"


class IconEntityType(str, enum.Enum):
    """Entity that an icon is linked to."""

    USER = "User"
    UNIT = "Unit"
    UNIT_GROUP = "UnitGroup"
    INSTANCE = "Instance"


class AgentStatus(str, enum.Enum):
    """
    Status of an agent. Users are Active or Blocked. Other agents stay
    Verified while they are allowed to act.
    """

    ACTIVE = "Active"
    UNVERIFIED = "Unverified"
    VERIFIED = "Verified"
    BLOCKED = "Blocked"


class OwnershipType(str, enum.Enum):
    """
    Ownership rules type
    """

    CREATOR = "Creator"
    UNIT = "Unit"
    UNIT_TO_INPUT_NODE = "UnitToInputNode"


class UnitIOTypeEnum(str, enum.Enum):
    """
    UnitIO types for database
    """

    OUTPUT = "Output"
    INPUT = "Input"


class UnitFirmwareUpdateStatus(str, enum.Enum):
    """
    Unit update status
    """

    REQUEST_SENT = "RequestSent"
    ERROR = "Error"
    SUCCESS = "Success"


class ReservedOutputBaseTopic(str, enum.Enum):
    """
    Booked output topics at Unit
    """

    STATE = "state"
    LOG = "log"


class BackendTopicCommand(str, enum.Enum):
    """
    Booked input topics at Unit
    """

    UPDATE = "Update"
    ENV_UPDATE = "EnvUpdate"
    SCHEMA_UPDATE = "SchemaUpdate"
    LOG_SYNC = "LogSync"
    RESET = "Reset"


class ReservedInputBaseTopic(str, enum.Enum):
    """
    Booked input topics at Unit
    """

    UPDATE = "update"
    ENV_UPDATE = "env_update"
    SCHEMA_UPDATE = "schema_update"
    LOG_SYNC = "log_sync"
    RESET = "reset"


class DestinationTopicType(str, enum.Enum):
    """
    Allowed types of mqtt topic destinations
    """

    INPUT_BASE_TOPIC = "input_base_topic"
    OUTPUT_BASE_TOPIC = "output_base_topic"
    INPUT_TOPIC = "input_topic"
    OUTPUT_TOPIC = "output_topic"


class GlobalPrefixTopic(str, enum.Enum):
    """
    Global topic prefixes
    """

    BACKEND_SUB_PREFIX = (
        "/pepeunit"  # forwards the mqtt message to the Pepeunit instance
    )


class StaticRepoFileName(str, enum.Enum):
    """
    Static files
    """

    SCHEMA_EXAMPLE = "schema_example.json"
    SCHEMA = "schema.json"
    ENV_EXAMPLE = "env_example.json"
    ENV = "env.json"


class ReservedStateKey(str, enum.Enum):
    """
    Reserved state Unit keys
    """

    IFCONFIG = "ifconfig"
    MILLIS = "millis"
    MEM_FREE = "mem_free"
    MEM_ALLOC = "mem_alloc"
    FREQ = "freq"
    STATVFS = "statvfs"
    PU_COMMIT_VERSION = "pu_commit_version"


class ReservedEnvVariableName(str, enum.Enum):
    """
    Reserved environment variable names in Unit
    """

    PU_DOMAIN = "PU_DOMAIN"
    PU_HTTP_TYPE = "PU_HTTP_TYPE"
    PU_APP_PREFIX = "PU_APP_PREFIX"
    PU_API_ACTUAL_PREFIX = "PU_API_ACTUAL_PREFIX"
    PU_MQTT_HOST = "PU_MQTT_HOST"
    PU_MQTT_PORT = "PU_MQTT_PORT"
    PU_MQTT_PING_INTERVAL = "PU_MQTT_PING_INTERVAL"
    PU_MQTT_KEEPALIVE = "PU_MQTT_KEEPALIVE"
    PU_AUTH_TOKEN = "PU_AUTH_TOKEN"
    PU_SECRET_KEY = "PU_SECRET_KEY"
    PU_ENCRYPT_KEY = "PU_ENCRYPT_KEY"
    PU_STATE_SEND_INTERVAL = "PU_STATE_SEND_INTERVAL"
    PU_MIN_LOG_LEVEL = "PU_MIN_LOG_LEVEL"
    PU_MAX_LOG_LENGTH = "PU_MAX_LOG_LENGTH"
    PU_COMMIT_VERSION = "PU_COMMIT_VERSION"


class CommandNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    START = "start"
    HELP = "help"
    REGISTRY = "registry"
    REPO = "repo"
    UNIT = "unit"
    INFO = "info"
    VERIFICATION = "verification"
    DASHBOARD = "dashboard"
    INSTANCES = "instances"
    ALERTS = "alerts"
    CONTROL = "control"


class EntityNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    REGISTRY = "Registry"
    REPO = "Repo"
    UNIT = "Unit"
    UNIT_IO = "UnitIO"
    UNIT_LOG = "UnitLog"
    DASHBOARD = "Dashboard"
    INSTANCE = "Instance"
    NOTIFICATION = "Notification"
    CONTROL = "Control"


class DecreesNames(str, enum.Enum):
    """
    Commands supported by the bot
    """

    RELATED_UNIT = "RelatedUnit"
    LOCAL_UPDATE = "LocalUpdate"
    SCAN = "Scan"
    SCAN_ALL = "ScanAll"
    INTEGRATION_TESTS = "IntegrationTests"
    UPDATE_ALL_REGISTRIES = "UpdateAllRegistries"
    UPDATE_ALL_UNITS_FIRMWARE = "UpdateAllUnitsFirmware"
    GET_ENV = "GetEnv"
    TAR = "Tar"
    TGZ = "Tgz"
    ZIP = "Zip"


class PermissionEntities(str, enum.Enum):
    """
    Types of entities to which accesses are assigned
    """

    USER = "User"
    UNIT = "Unit"
    REPO = "Repo"
    UNIT_IO = "UnitIO"


class GitPlatform(str, enum.Enum):
    """
    Types git platforms
    """

    GITLAB = "Gitlab"
    GITHUB = "Github"


class LogLevel(str, enum.Enum):
    """
    Types of log levels
    """

    DEBUG = "Debug"
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"
    CRITICAL = "Critical"


class DataPipeStatus(str, enum.Enum):
    """
    Types of state data pipeline
    """

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    ERROR = "Error"


class DataPipeStage(str, enum.Enum):
    """
    Stages data pipeline
    """

    ACTIVE_PERIOD = "ActivePeriod"
    FILTERS = "Filters"
    TRANSFORMATIONS = "Transformations"
    PROCESSING_POLICY = "ProcessingPolicy"
    ALERTS = "Alerts"


class ActivePeriodType(str, enum.Enum):
    PERMANENT = "Permanent"
    FROM_DATE = "FromDate"
    TO_DATE = "ToDate"
    DATE_RANGE = "DateRange"


class TypeInputValue(str, enum.Enum):
    TEXT = "Text"
    NUMBER = "Number"


class FilterTypeValueFiltering(str, enum.Enum):
    WHITELIST = "WhiteList"
    BLACKLIST = "BlackList"


class FilterTypeValueThreshold(str, enum.Enum):
    MIN = "Min"
    MAX = "Max"
    RANGE = "Range"


class ProcessingPolicyType(str, enum.Enum):
    LAST_VALUE = "LastValue"
    N_RECORDS = "NRecords"
    TIME_WINDOW = "TimeWindow"
    AGGREGATION = "Aggregation"


class AggregationFunctions(str, enum.Enum):
    AVG = "Avg"
    MIN = "Min"
    MAX = "Max"
    SUM = "Sum"


class DatasourceFormat(str, enum.Enum):
    TIME_SERIES = "timeseries"


class RepositoryRegistryStatus(str, enum.Enum):
    """
    Types of state RepositoryRegistry
    """

    UPDATED = "Updated"
    PROCESSING = "Processing"
    ERROR = "Error"


class CredentialStatus(str, enum.Enum):
    """
    Types of state CredentialStatus
    """

    VALID = "Valid"
    NOT_VERIFIED = "NotVerified"
    ERROR = "Error"


class RepositoryRegistryType(str, enum.Enum):
    """
    Types of log levels
    """

    PRIVATE = "Private"
    PUBLIC = "Public"


class GrafanaUserRole(str, enum.Enum):
    """
    Role User for Grafana
    """

    VIEWER = "Viewer"
    EDITOR = "Editor"
    ADMIN = "Admin"


class CookieName(str, enum.Enum):
    """
    All Cookies names
    """

    PEPEUNIT_GRAFANA = "PepeunitGrafana"


class DashboardPanelTypeEnum(str, enum.Enum):
    """
    All dashboard panel types
    """

    # Regular graph
    TIME_SERIES = "timeseries"
    # Bar graph
    BAR_CHART = "barchart"
    # Single value without a graph
    STAT = "stat"
    # Speedometer, has a minimum and a maximum, calculated automatically from the selection
    GAUGE = "gauge"
    # Like gauge, but as a bar
    BAR_GAUGE = "bargauge"
    # Table
    TABLE = "table"
    # Segmented donut
    PIE_CHART = "piechart"
    # Categorizing, like heatmap, but allows setting a threshold value
    STATE_TIMELINE = "state-timeline"
    # Regular heatmap, data source covers all data
    HEATMAP = "heatmap"
    # Similar to state-timeline, but differs at least in merging dates
    STATUS_HISTORY = "status-history"
    # View distributions in selections
    HISTOGRAM = "histogram"
    # Text in md format
    TEXT = "text"
    # List of alerts
    ALERT_LIST = "alertlist"
    # Allows making a set of links to existing dashboards
    DASHBOARD_LIST = "dashlist"
    # News in rss format
    NEWS = "news"
    # List with filtering support
    ANNOTATION_LIST = "annolist"
    # Stock market chart
    CANDLESTICK = "candlestick"
    # Canvas for drawing
    CANVAS = "canvas"
    # Displays folder-like structures well
    FLAME_GRAPH = "flamegraph"
    # World map
    GEOMAP = "geomap"
    # Logs
    LOGS = "logs"
    # Proper heatmap, 24 hours by days
    HOURLY_HEATMAP = "marcusolsson-hourly-heatmap-panel"
    # Graphs
    NODE_GRAPH = "nodeGraph"
    # Like request execution time in the browser console
    TRACES = "traces"
    # Like timeseries, but numbers instead of time
    TREND = "trend"
    # Scatter plot
    XY_CHART = "xychart"


class DashboardStatus(str, enum.Enum):
    """
    Types of state Dashboard sync
    """

    SUCCESS = "Success"
    PROCESSING = "Processing"
    ERROR = "Error"


class InstanceTrustStatus(str, enum.Enum):
    TRUST = "Trust"
    PENDING = "Pending"
    BLOCKING = "Blocking"


class InstanceCollectionStatus(str, enum.Enum):
    SUCCESS = "Success"
    TIMEOUT = "Timeout"
    ERROR = "Error"
    BLOCKING = "Blocking"


class OperationTaskStatus(str, enum.Enum):
    RUNNING = "Running"
    SUCCESS = "Success"
    ERROR = "Error"


class OperationTaskType(str, enum.Enum):
    INTEGRATION_TESTS = "IntegrationTests"
    SCAN_ALL_INSTANCES = "ScanAllInstances"
    SCAN_INSTANCE = "ScanInstance"
    UPDATE_ALL_REGISTRIES = "UpdateAllRegistries"
    UPDATE_REGISTRY = "UpdateRegistry"
    UPDATE_UNITS_FIRMWARE = "UpdateUnitsFirmware"
    UPDATE_ALL_UNITS_FIRMWARE = "UpdateAllUnitsFirmware"
    REBOOT_INSTANCE = "RebootInstance"


class IntegrationTestsStatus(str, enum.Enum):
    SUCCESS = "Success"
    RUNNING = "Running"
    WARNING = "Warning"
    ERROR = "Error"


class CacheKey(str, enum.Enum):
    INSTANCE_METRICS = "InstanceMetrics"
    INSTANCE_METRICS_PUBLIC = "InstanceMetricsPublic"


class NotificationType(str, enum.Enum):
    """
    What a notification shows
    """

    INSTANCE_DAILY_STATE = "InstanceDailyState"
    UNIT_DAILY_SUMMARY = "UnitDailySummary"
    DATA_PIPE_ALERT = "DataPipeAlert"
    INTEGRATION_TESTS = OperationTaskType.INTEGRATION_TESTS.value
    SCAN_ALL_INSTANCES = OperationTaskType.SCAN_ALL_INSTANCES.value
    SCAN_INSTANCE = OperationTaskType.SCAN_INSTANCE.value
    UPDATE_ALL_REGISTRIES = OperationTaskType.UPDATE_ALL_REGISTRIES.value
    UPDATE_REGISTRY = OperationTaskType.UPDATE_REGISTRY.value
    UPDATE_UNITS_FIRMWARE = OperationTaskType.UPDATE_UNITS_FIRMWARE.value
    UPDATE_ALL_UNITS_FIRMWARE = (
        OperationTaskType.UPDATE_ALL_UNITS_FIRMWARE.value
    )
    REBOOT_INSTANCE = OperationTaskType.REBOOT_INSTANCE.value


class FileLock(str, enum.Enum):
    INIT = "tmp/init_lock.lock"
    MQTT_RUN = "tmp/mqtt_run_lock.lock"
    MQTT_SUBSCRIBE = "tmp/mqtt_subscribe.lock"
    UPDATE_REPOS = "tmp/update_repos.lock"
    UPDATE_REGISTRY = "tmp/update_registry.lock"
    COLLECT_INSTANCES = "tmp/collect_instances.lock"
    NOTIFICATION_SCHEDULE = "tmp/notification_schedule.lock"
    NOTIFICATION_PROCESS = "tmp/notification_process.lock"
