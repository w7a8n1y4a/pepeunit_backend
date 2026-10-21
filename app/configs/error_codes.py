"""Stable numeric codes for errors shown to users.

A code is ``DDDLLL``: domain ``DDD`` is 100–999, local number ``LLL`` is 100–999.
The client translates by this number. The English text stays a fallback.

Each entity owns one domain. That number sits in the band of the entity's
first letter. Every letter keeps at least one number, and a letter that
already has several entities keeps at least one number for each of them.
The numbers left after that are split with the Hamilton method by the
Wikipedia table "Relative frequencies of the first letters of a word in the
English language", Texts column. An equal remainder goes to the letter later
in the alphabet. Inside a band the existing entities are spread apart, so a
future entity of the same letter has a free number between them.
"""

from enum import IntEnum, nonmember, unique
from functools import cache

from pydantic_core import PydanticCustomError

from app.dto.enum import ErrorEntity, JsonPayload, NotFoundEntity, UuidEntity


@unique
class ErrorCode(IntEnum):
    # Access, domain 100. Band 100–201.
    ACCESS_TOKEN_EXPIRED = 100_100
    ACCESS_TOKEN_INVALID = 100_101
    ACCESS_AGENT_BLOCKED_OR_NOT_FOUND = 100_102
    ACCESS_USER_BLOCKED = 100_103
    ACCESS_USER_NOT_FOUND = 100_104
    ACCESS_UNIT_NOT_FOUND = 100_105
    ACCESS_INVALID_AGENT_TYPE = 100_106
    ACCESS_UNKNOWN_AGENT_TYPE = 100_107
    ACCESS_AGENT_TYPE_NOT_ALLOWED = 100_108
    ACCESS_ROLE_NOT_ALLOWED = 100_109
    ACCESS_NOT_CREATOR = 100_110
    ACCESS_UNIT_REQUEST_DENIED = 100_111
    ACCESS_UNIT_INPUT_DENIED = 100_112
    ACCESS_VISIBILITY_LEVEL_NOT_ALLOWED = 100_113
    ACCESS_PRIVATE_REPO = 100_114
    ACCESS_PRIVATE_VISIBILITY = 100_115
    ACCESS_REPO_ONLY = 100_116
    ACCESS_REPO_USERS_ONLY = 100_117
    ACCESS_REPO_NO_CREDENTIALS = 100_118
    ACCESS_NO_PLATFORM_CREDENTIALS = 100_119
    ACCESS_PLATFORM_CREDENTIALS_STATUS = 100_120
    ACCESS_NOTIFICATION_NOT_ALLOWED = 100_121
    ACCESS_ICON_OWNER_ONLY = 100_122
    ACCESS_DOCKED_UNIT_ONLY = 100_123
    ACCESS_TOPIC_DESTINATION_INVALID = 100_124
    ACCESS_CHALLENGE_INVALID = 100_125
    ACCESS_CHALLENGE_DOMAIN_MISMATCH = 100_126
    ACCESS_CHALLENGE_USED_OR_EXPIRED = 100_127
    ACCESS_CHALLENGE_EXPIRED = 100_128
    ACCESS_SIGNATURE_MISMATCH = 100_129
    # Cipher, domain 241. Band 241–286.
    CIPHER_CONTENT_TOO_LONG = 241_100
    CIPHER_ENV_JSON_INVALID = 241_101
    # Data pipe, domain 316. Band 287–316. Go uses 316_5xx.
    DATAPIPE_BULK_CREATE_LAST_VALUE_UNAVAILABLE = 316_100
    DATAPIPE_NO_DATA = 316_101
    DATAPIPE_TOPIC_SUFFIX = 316_102
    DATAPIPE_NOT_ACTIVE = 316_103
    DATAPIPE_NOT_FILLED = 316_104
    DATAPIPE_LAST_VALUE_UNSUPPORTED = 316_105
    DATAPIPE_IS_NONE = 316_106
    DATAPIPE_CONFIG_INVALID = 316_107
    DATAPIPE_CONFIG_JSON_INVALID = 316_108
    DATAPIPE_ACTIVE_FROM_DATE_START = 316_120
    DATAPIPE_ACTIVE_TO_DATE_END = 316_121
    DATAPIPE_ACTIVE_RANGE_BOUNDS = 316_122
    DATAPIPE_ACTIVE_RANGE_ORDER = 316_123
    DATAPIPE_FILTER_VALUES_NUMBER = 316_124
    DATAPIPE_FILTER_VALUES_TEXT = 316_125
    DATAPIPE_THRESHOLD_MIN_REQUIRED = 316_126
    DATAPIPE_THRESHOLD_MAX_REQUIRED = 316_127
    DATAPIPE_THRESHOLD_RANGE_REQUIRED = 316_128
    DATAPIPE_THRESHOLD_RANGE_ORDER = 316_129
    DATAPIPE_MAX_SIZE = 316_130
    DATAPIPE_N_RECORDS_REQUIRED = 316_131
    DATAPIPE_N_RECORDS_RANGE = 316_132
    DATAPIPE_TIME_WINDOW_REQUIRED = 316_133
    DATAPIPE_TIME_WINDOW_INVALID = 316_134
    DATAPIPE_AGGREGATION_FUNCTIONS_REQUIRED = 316_135
    DATAPIPE_FILTERING_VALUES_REQUIRED = 316_136
    DATAPIPE_THRESHOLD_NOT_FOR_TEXT = 316_137
    DATAPIPE_CSV_WINDOW_DATETIME = 316_160
    DATAPIPE_CSV_N_RECORDS_LIMIT = 316_161
    DATAPIPE_CSV_WINDOW_SECONDS = 316_162
    DATAPIPE_CSV_WINDOW_ORDER = 316_163
    DATAPIPE_CSV_WINDOW_MIN_DELTA = 316_164
    DATAPIPE_CSV_WINDOW_SIZE_MISMATCH = 316_165
    DATAPIPE_CSV_PREVIOUS_WINDOW_SIZE = 316_166
    DATAPIPE_CSV_MAX_RATE = 316_167
    DATAPIPE_CSV_LAST_UNIQUE = 316_168
    DATAPIPE_CSV_MAX_SIZE = 316_169
    DATAPIPE_CSV_NOT_MONOTONIC = 316_170
    DATAPIPE_CSV_BEFORE_ACTIVE_START = 316_171
    DATAPIPE_CSV_AFTER_ACTIVE_END = 316_172
    DATAPIPE_CSV_OUTSIDE_ACTIVE_RANGE = 316_173
    DATAPIPE_CSV_NOT_IN_WHITELIST = 316_174
    DATAPIPE_CSV_IN_BLACKLIST = 316_175
    DATAPIPE_CSV_BELOW_THRESHOLD = 316_176
    DATAPIPE_CSV_ABOVE_THRESHOLD = 316_177
    DATAPIPE_CSV_OUTSIDE_THRESHOLD = 316_178
    DATAPIPE_CSV_STATE_NOT_TEXT = 316_179
    DATAPIPE_CSV_STATE_NOT_NUMBER = 316_180
    DATAPIPE_CSV_DATETIME_INVALID = 316_181
    DATAPIPE_RELATIVE_TIME_INVALID = 316_182
    # Feature flag, domain 342. Band 342–377.
    FEATURE_DISABLED = 342_100
    # Git platform, domain 378. Band 378–394.
    GIT_PLATFORM_TIMEOUT = 378_100
    GIT_PLATFORM_REQUEST_FAILED = 378_101
    GIT_PLATFORM_INVALID_CREDENTIALS = 378_102
    GIT_PLATFORM_RATE_LIMIT = 378_103
    # Git repository, domain 386.
    GIT_REPO_VERSION_MISSING = 386_100
    GIT_REPO_COMMIT_WITHOUT_TAG = 386_101
    GIT_REPO_COMMIT_NOT_FOUND = 386_102
    GIT_REPO_SCHEMA_UNRESOLVED_KEYS = 386_103
    GIT_REPO_SCHEMA_VALUE_TYPE = 386_104
    GIT_REPO_TOPIC_CHARS = 386_105
    GIT_REPO_TOPIC_TOO_LONG = 386_106
    GIT_REPO_ENV_UNRESOLVED = 386_107
    GIT_REPO_BRANCH_NOT_FOUND = 386_108
    GIT_REPO_COMMIT_NOT_IN_BRANCH = 386_109
    GIT_REPO_TAG_NO_PLATFORMS = 386_110
    GIT_REPO_PLATFORM_NOT_FOUND = 386_111
    GIT_REPO_NOT_EXIST = 386_112
    GIT_REPO_INVALID_URL_OR_CREDENTIALS = 386_113
    GIT_REPO_FILE_NOT_FOUND = 386_114
    GIT_REPO_TOO_LARGE = 386_115
    GIT_REPO_SCHEMA_JSON_INVALID = 386_116
    GIT_REPO_ENV_EXAMPLE_JSON_INVALID = 386_117
    GIT_REPO_ENV_JSON_INVALID = 386_118
    GIT_REPO_COMMIT_MISSING = 386_119
    # Grafana, domain 394.
    GRAFANA_NAME_INVALID = 394_100
    GRAFANA_TITLE_INVALID = 394_101
    GRAFANA_UNIT_IO_NOT_UNIQUE = 394_102
    GRAFANA_PANEL_UNIT_IO_LIMIT = 394_103
    GRAFANA_RETRIES_EXHAUSTED = 394_104
    GRAFANA_VALUE_NOT_SUPPORTED = 394_105
    GRAFANA_DATA_TYPE_NOT_SUPPORTED = 394_106
    GRAFANA_DASHBOARD_HAS_NO_PANELS = 394_107
    GRAFANA_NO_ACTIVE_DATAPIPE = 394_108
    GRAFANA_INVALID_DATAPIPE_YML = 394_109
    GRAFANA_NAME_NOT_UNIQUE = 394_110
    GRAFANA_TITLE_NOT_UNIQUE = 394_111
    # Dashboard, domain 287.
    DASHBOARD_NOT_FOUND = 287_100
    DASHBOARD_PANEL_NOT_FOUND = 287_101
    PANELS_UNIT_IOS_NOT_FOUND = 287_102
    DASHBOARD_UUID_INVALID = 287_110
    # Icon, domain 432. Band 432–496. Instance is 496.
    ICON_TOO_LARGE = 432_100
    ICON_NOT_PNG = 432_101
    ICON_WRONG_SIZE = 432_102
    ICON_TARGET_UNSUPPORTED = 432_103
    ICON_NOT_FOUND = 432_104
    # Instance, domain 496.
    INSTANCE_CACHE_NOT_INITIALIZED = 496_100
    INSTANCE_URL_EXISTS = 496_101
    INSTANCE_INTEGRATION_TESTS_FAILED = 496_102
    INSTANCE_COLLECTION_TRUST = 496_103
    INSTANCE_COLLECTION_FAILED = 496_104
    INSTANCE_TRUST_STATUS_INVALID = 496_105
    INSTANCE_URL_SCHEME = 496_106
    INSTANCE_URL_HOST = 496_107
    INSTANCE_URL_QUERY = 496_108
    INSTANCE_URL_CREDENTIALS = 496_109
    INSTANCE_URL_ENDPOINT = 496_110
    INSTANCE_NOT_FOUND = 496_111
    INSTANCE_SETTINGS_NOT_FOUND = 496_112
    INSTANCE_SETTINGS_INVALID = 496_113
    INSTANCE_RESPONSE_TOO_LARGE = 496_114
    INSTANCE_SETTINGS_EMAIL_INVALID = 496_120
    INSTANCE_SETTINGS_TELEGRAM_TOKEN_INVALID = 496_121
    INSTANCE_SETTINGS_COUNT_RATE_INVALID = 496_122
    INSTANCE_SETTINGS_BYTES_RATE_INVALID = 496_123
    INSTANCE_SETTINGS_GRAFANA_CREDENTIALS = 496_124
    INSTANCE_SETTINGS_GITHUB_TOKEN_PAIR = 496_125
    # MQTT, domain 532. Band 532–565.
    MQTT_RATE_LIMIT = 532_100
    MQTT_PAYLOAD_TOO_LARGE = 532_101
    MQTT_TOPIC_DOMAIN = 532_102
    MQTT_STATE_NO_COMMIT = 532_103
    MQTT_PUBLISH_LOOP_NOT_INITIALIZED = 532_104
    MQTT_PUBLISH_DISCONNECTED = 532_105
    MQTT_PUBLISH_TIMEOUT = 532_106
    MQTT_PUBLISH_FAILED = 532_107
    MQTT_SESSION_INVALID = 532_108
    MQTT_UNIT_TOPIC_ONLY = 532_109
    MQTT_TOPIC_STRUCT = 532_110
    MQTT_HARDWARE_STATE_INVALID = 532_111
    MQTT_UNIT_LOG_INVALID = 532_112
    # Notification, domain 566. Band 566–586.
    NOTIFICATION_NOT_FOUND = 566_100
    NOTIFICATION_TIME_INVALID = 566_101
    # Operation task, domain 587. Band 587–653.
    OPERATION_TASK_COOLDOWN = 587_100
    OPERATION_TASK_NOT_FOUND = 587_101
    # Permission, domain 692. Band 654–692.
    PERMISSION_AGENT_TYPE_INVALID = 692_100
    PERMISSION_RESOURCE_TYPE_INVALID = 692_101
    PERMISSION_EXISTS = 692_102
    PERMISSION_SELF_ACCESS = 692_103
    PERMISSION_CREATOR_ACCESS = 692_104
    PERMISSION_UNIT_CHILD_IO = 692_105
    PERMISSION_NOT_FOUND = 692_106
    PERMISSION_AGENT_UUID_INVALID = 692_110
    PERMISSION_RESOURCE_UUID_INVALID = 692_111
    # Pagination, domain 654.
    PAGINATION_OFFSET = 654_100
    PAGINATION_LIMIT_NEGATIVE = 654_101
    PAGINATION_LIMIT_TOO_LARGE = 654_102
    # Readme, domain 696. Band 696–721.
    README_FIELD_TOO_LONG = 696_100
    README_FIELD_TOO_MANY_ITEMS = 696_101
    README_TOML_TOO_LARGE = 696_102
    README_TOML_INVALID = 696_103
    # Repo, domain 721.
    REPO_URL_EXISTS = 721_100
    REPO_IS_PUBLIC = 721_101
    REPO_PLATFORM_UNSUPPORTED = 721_102
    REPO_SYNC_FAILED = 721_103
    REPO_URL_INVALID = 721_104
    REPO_CREDENTIALS_INVALID = 721_105
    REPO_PUBLIC = 721_106
    REPO_CREDENTIALS_MISSING = 721_107
    REPO_NO_VALID_CREDENTIALS = 721_108
    REPO_SYNC_TOO_SOON = 721_109
    REPO_USER_NO_CREDENTIALS = 721_110
    REPO_CREDENTIALS_ERROR = 721_111
    REPO_CREDENTIALS_NOT_VERIFIED = 721_112
    REPO_NOT_FOUND = 721_113
    REPO_HAS_UNITS = 721_114
    REPO_RELEASES_MISSING = 721_115
    REPO_RELEASES_JSON_INVALID = 721_116
    REPO_CREDENTIALS_JSON_INVALID = 721_117
    REPO_PRIVATE_REPO_JSON_INVALID = 721_118
    REPO_UUID_INVALID = 721_120
    # Unit, domain 920. Band 920–933.
    UNIT_NOT_FOUND = 920_100
    UNIT_NAME_INVALID = 920_101
    UNIT_AUTOUPDATE_TAGS_ONLY = 920_102
    UNIT_MANUAL_UPDATE_BRANCH_COMMIT = 920_103
    UNIT_WBITS_INVALID = 920_104
    UNIT_LEVEL_INVALID = 920_105
    UNIT_VISIBILITY_PARENT_BELOW_CHILD = 920_106
    UNIT_NAME_NOT_UNIQUE = 920_107
    UNIT_UUID_INVALID = 920_110
    # Unit group, domain 924.
    UNIT_GROUP_NOT_FOUND = 924_100
    UNIT_GROUP_NAME_INVALID = 924_101
    UNIT_GROUP_UNIT_ALREADY_IN_GROUP = 924_102
    UNIT_GROUP_COUNT_LIMIT = 924_103
    UNIT_GROUP_LINK_NOT_FOUND = 924_104
    UNIT_GROUP_NAME_NOT_UNIQUE = 924_105
    UNIT_GROUP_UUID_INVALID = 924_110
    # Unit IO, domain 929.
    UNIT_IO_NOT_FOUND = 929_100
    UNIT_IO_MAX_CONNECTIONS = 929_101
    UNIT_IO_INPUT_CONNECTION_LIMIT = 929_102
    UNIT_IO_OUTPUT_CONNECTION_LIMIT = 929_103
    UNIT_IO_EDGE_EXISTS = 929_104
    UNIT_IO_NOT_INPUT = 929_105
    UNIT_IO_NOT_OUTPUT = 929_106
    UNIT_IO_EDGE_NOT_FOUND = 929_107
    UNIT_IO_STATE_JSON_INVALID = 929_108
    UNIT_IO_UUID_INVALID = 929_110
    UNIT_IO_INPUT_UUID_INVALID = 929_111
    UNIT_IO_OUTPUT_UUID_INVALID = 929_112
    # User, domain 933.
    USER_NOT_FOUND = 933_100
    USER_LOGIN_INVALID = 933_101
    USER_TELEGRAM_ALREADY_LINKED = 933_102
    USER_PUBLIC_KEY_NOT_UNIQUE = 933_103
    USER_COUNT_LIMIT = 933_104
    USER_PUBLIC_KEY_INVALID = 933_105
    USER_PUBLIC_KEY_HASH_INVALID = 933_106
    USER_VERIFICATION_CODE_NOT_FOUND = 933_107
    USER_UUID_INVALID = 933_110

    domain_min = nonmember(100)
    domain_max = nonmember(999)
    local_min = nonmember(100)
    local_max = nonmember(999)
    log_prefix = nonmember("PUER")
    validation_prefix = nonmember("error.")

    # Percent of English words that start with the letter. Texts column.
    first_letter_frequency_percent = nonmember(
        {
            "A": 11.7,
            "B": 4.4,
            "C": 5.2,
            "D": 3.2,
            "E": 2.8,
            "F": 4.0,
            "G": 1.6,
            "H": 4.2,
            "I": 7.3,
            "J": 0.51,
            "K": 0.86,
            "L": 2.4,
            "M": 3.8,
            "N": 2.3,
            "O": 7.6,
            "P": 4.3,
            "Q": 0.22,
            "R": 2.8,
            "S": 6.7,
            "T": 16.0,
            "U": 1.2,
            "V": 0.82,
            "W": 5.5,
            "X": 0.045,
            "Y": 0.76,
            "Z": 0.045,
        }
    )

    @staticmethod
    def _letters() -> list[str]:
        return [chr(ord("A") + offset) for offset in range(26)]

    @staticmethod
    def _spread(width: int, count: int) -> list[int]:
        """Positions of the entities already in a band. Gaps stay free."""
        if count <= 1:
            return [0]

        last_position = width - 1
        gaps_between = count - 1
        return [
            round(place * last_position / gaps_between)
            for place in range(count)
        ]

    @staticmethod
    def _reserved_widths(letters: list[str]) -> dict[str, int]:
        """One number per letter, plus one for each entity that letter has."""
        counts = dict.fromkeys(letters, 0)
        for entity in ErrorEntity:
            counts[entity[0]] += 1
        return {letter: max(1, counts[letter]) for letter in letters}

    @classmethod
    def _spare_widths(cls, letters: list[str], spare: int) -> dict[str, int]:
        """Leftover domain numbers, shared by first-letter frequency.

        Each letter keeps the whole part of its share. The numbers that
        remain go to the largest fractions. An equal fraction goes to the
        letter later in the alphabet.
        """
        frequency = cls.first_letter_frequency_percent
        total = sum(frequency.values())
        exact_share = {
            letter: frequency[letter] / total * spare for letter in letters
        }
        whole_share = {letter: int(exact_share[letter]) for letter in letters}
        leftover = spare - sum(whole_share.values())
        by_fraction = sorted(
            letters,
            key=lambda letter: (
                exact_share[letter] - whole_share[letter],
                letter,
            ),
            reverse=True,
        )
        for letter in by_fraction[:leftover]:
            whole_share[letter] += 1
        return whole_share

    @classmethod
    def _lay_out_bands(
        cls,
        letters: list[str],
        reserved: dict[str, int],
        extra: dict[str, int],
    ) -> dict[str, range]:
        bands: dict[str, range] = {}
        start = cls.domain_min
        for letter in letters:
            width = reserved[letter] + extra[letter]
            bands[letter] = range(start, start + width)
            start += width
        return bands

    @classmethod
    @cache
    def letter_bands(cls) -> dict[str, range]:
        """Domain numbers owned by each first letter."""
        letters = cls._letters()
        reserved = cls._reserved_widths(letters)
        domain_count = cls.domain_max - cls.domain_min + 1
        spare = domain_count - sum(reserved.values())
        extra = cls._spare_widths(letters, spare)
        return cls._lay_out_bands(letters, reserved, extra)

    @classmethod
    @cache
    def entity_domains(cls) -> dict[ErrorEntity, tuple[str, int]]:
        """One domain per entity, spread across that letter's band."""
        bands = cls.letter_bands()
        by_letter: dict[str, list[ErrorEntity]] = {}
        for entity in ErrorEntity:
            by_letter.setdefault(entity[0], []).append(entity)

        assigned: dict[ErrorEntity, tuple[str, int]] = {}
        for letter, entities in by_letter.items():
            band = bands[letter]
            ordered = sorted(entities)
            positions = cls._spread(len(band), len(ordered))
            for entity, position in zip(ordered, positions, strict=True):
                assigned[entity] = (letter, band[position])
        return assigned

    @classmethod
    @cache
    def catalog(cls) -> dict[str, int]:
        """Every user-facing code, computed once and reused."""
        return {code.name: int(code) for code in cls}

    @staticmethod
    def console(code: ErrorCode | int) -> str:
        """Log text. The API response keeps the bare number."""
        return f"{ErrorCode.log_prefix}{int(code)}"

    @staticmethod
    def coded(code: ErrorCode, message: str) -> PydanticCustomError:
        """Pydantic validator failure that keeps the numeric code."""
        error_type = f"{ErrorCode.validation_prefix}{int(code)}"
        return PydanticCustomError(error_type, message)

    @staticmethod
    def code_from_validation(error: dict, fallback: ErrorCode) -> ErrorCode:
        """The code stored by coded, or the fallback for pydantic's own type."""
        error_type = str(error.get("type", ""))
        prefix = ErrorCode.validation_prefix
        if not error_type.startswith(prefix):
            return fallback
        return ErrorCode(int(error_type.removeprefix(prefix)))


# Attached after the members exist, so each value is that member.
ErrorCode.not_found = {
    NotFoundEntity.USER: ErrorCode.USER_NOT_FOUND,
    NotFoundEntity.UNIT: ErrorCode.UNIT_NOT_FOUND,
    NotFoundEntity.UNIT_IO: ErrorCode.UNIT_IO_NOT_FOUND,
    NotFoundEntity.UNIT_GROUP: ErrorCode.UNIT_GROUP_NOT_FOUND,
    NotFoundEntity.UNIT_GROUP_UNIT: ErrorCode.UNIT_GROUP_LINK_NOT_FOUND,
    NotFoundEntity.UNIT_IO_EDGE: ErrorCode.UNIT_IO_EDGE_NOT_FOUND,
    NotFoundEntity.REPO: ErrorCode.REPO_NOT_FOUND,
    NotFoundEntity.DASHBOARD: ErrorCode.DASHBOARD_NOT_FOUND,
    NotFoundEntity.DASHBOARD_PANEL: ErrorCode.DASHBOARD_PANEL_NOT_FOUND,
    NotFoundEntity.PANELS_UNIT_IOS: ErrorCode.PANELS_UNIT_IOS_NOT_FOUND,
    NotFoundEntity.ICON: ErrorCode.ICON_NOT_FOUND,
    NotFoundEntity.NOTIFICATION: ErrorCode.NOTIFICATION_NOT_FOUND,
    NotFoundEntity.INSTANCE: ErrorCode.INSTANCE_NOT_FOUND,
    NotFoundEntity.INSTANCE_SETTINGS: ErrorCode.INSTANCE_SETTINGS_NOT_FOUND,
    NotFoundEntity.PERMISSION: ErrorCode.PERMISSION_NOT_FOUND,
    NotFoundEntity.OPERATION_TASK: ErrorCode.OPERATION_TASK_NOT_FOUND,
    NotFoundEntity.COMMIT: ErrorCode.GIT_REPO_COMMIT_MISSING,
    NotFoundEntity.RELEASES: ErrorCode.REPO_RELEASES_MISSING,
    NotFoundEntity.VERIFICATION_CODE: ErrorCode.USER_VERIFICATION_CODE_NOT_FOUND,
}

ErrorCode.uuid_invalid = {
    UuidEntity.UNIT: ErrorCode.UNIT_UUID_INVALID,
    UuidEntity.UNIT_IO: ErrorCode.UNIT_IO_UUID_INVALID,
    UuidEntity.UNIT_GROUP: ErrorCode.UNIT_GROUP_UUID_INVALID,
    UuidEntity.USER: ErrorCode.USER_UUID_INVALID,
    UuidEntity.REPO: ErrorCode.REPO_UUID_INVALID,
    UuidEntity.DASHBOARD: ErrorCode.DASHBOARD_UUID_INVALID,
    UuidEntity.PERMISSION_AGENT: ErrorCode.PERMISSION_AGENT_UUID_INVALID,
    UuidEntity.PERMISSION_RESOURCE: ErrorCode.PERMISSION_RESOURCE_UUID_INVALID,
    UuidEntity.UNIT_IO_INPUT: ErrorCode.UNIT_IO_INPUT_UUID_INVALID,
    UuidEntity.UNIT_IO_OUTPUT: ErrorCode.UNIT_IO_OUTPUT_UUID_INVALID,
}

ErrorCode.json_invalid = {
    JsonPayload.HARDWARE_STATE: ErrorCode.MQTT_HARDWARE_STATE_INVALID,
    JsonPayload.UNIT_HARDWARE_LOG: ErrorCode.MQTT_UNIT_LOG_INVALID,
    JsonPayload.DATA_PIPE_CONFIG: ErrorCode.DATAPIPE_CONFIG_JSON_INVALID,
    JsonPayload.UNIT_IO_STATE: ErrorCode.UNIT_IO_STATE_JSON_INVALID,
    JsonPayload.CIPHER_ENV: ErrorCode.CIPHER_ENV_JSON_INVALID,
    JsonPayload.RELEASES_FOR_COMPILE_REPO: (
        ErrorCode.REPO_RELEASES_JSON_INVALID
    ),
    JsonPayload.RELEASES_FOR_COMPILE_REPO_TITLE: (
        ErrorCode.REPO_RELEASES_JSON_INVALID
    ),
    JsonPayload.CIPHER_CREDENTIALS_PRIVATE_REPOSITORY: (
        ErrorCode.REPO_CREDENTIALS_JSON_INVALID
    ),
    JsonPayload.OLD_CREDENTIALS_STRUCT: (
        ErrorCode.REPO_CREDENTIALS_JSON_INVALID
    ),
    JsonPayload.PRIVATE_REPO: (ErrorCode.REPO_PRIVATE_REPO_JSON_INVALID),
    JsonPayload.ENV: ErrorCode.GIT_REPO_ENV_JSON_INVALID,
    JsonPayload.ENV_EXAMPLE: ErrorCode.GIT_REPO_ENV_EXAMPLE_JSON_INVALID,
    JsonPayload.SCHEMA_EXAMPLE: ErrorCode.GIT_REPO_SCHEMA_JSON_INVALID,
}
