CREATE TABLE n_last_entry
(
    uuid UUID,
    unit_node_uuid UUID,
    state String,
    state_type Enum8('Number' = 1, 'Text' = 2),
    create_datetime DateTime64(3),
    max_count UInt32,
    size UInt32,
)
ENGINE = MergeTree()
ORDER BY (unit_node_uuid, create_datetime, uuid)
PRIMARY KEY (unit_node_uuid, create_datetime)
SETTINGS
    merge_with_ttl_timeout = 600,
    index_granularity = 128;

CREATE TABLE window_entry
(
    uuid UUID,
    unit_node_uuid UUID,
    state String,
    state_type Enum8('Number' = 1, 'Text' = 2),
    create_datetime DateTime64(3),
    expiration_datetime DateTime,
    size UInt32
)
ENGINE = MergeTree()
ORDER BY (unit_node_uuid, create_datetime, uuid)
PRIMARY KEY (unit_node_uuid, create_datetime)
TTL expiration_datetime
SETTINGS
    merge_with_ttl_timeout = 600,
    index_granularity = 128;

CREATE TABLE aggregation_entry
(
    uuid UUID,
    unit_node_uuid UUID,
    state Float64,
    aggregation_type Enum8('Avg' = 1, 'Min' = 2, 'Max' = 3, 'Sum' = 4),
    time_window_size UInt32,
    create_datetime DateTime64(3),
    start_window_datetime DateTime64(3),
    end_window_datetime DateTime64(3)
)
ENGINE = MergeTree()
ORDER BY (unit_node_uuid, start_window_datetime, uuid)
PRIMARY KEY (unit_node_uuid, start_window_datetime)
SETTINGS
    index_granularity = 128;