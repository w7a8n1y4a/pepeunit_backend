CREATE TABLE n_last_entry_new
(
    unit_node_uuid UUID,
    state String,
    state_type Enum8('Number' = 1, 'Text' = 2),
    create_datetime DateTime64(3),
    max_count UInt32,
    size UInt32
)
ENGINE = MergeTree()
ORDER BY (unit_node_uuid, create_datetime)
PRIMARY KEY (unit_node_uuid, create_datetime)
SETTINGS
    merge_with_ttl_timeout = 600,
    index_granularity = 128;

INSERT INTO n_last_entry_new
SELECT
    unit_node_uuid,
    state,
    state_type,
    create_datetime,
    max_count,
    size
FROM n_last_entry;

RENAME TABLE n_last_entry TO n_last_entry_old, n_last_entry_new TO n_last_entry;

DROP TABLE n_last_entry_old;


CREATE TABLE window_entry_new
(
    unit_node_uuid UUID,
    state String,
    state_type Enum8('Number' = 1, 'Text' = 2),
    create_datetime DateTime64(3),
    expiration_datetime DateTime,
    size UInt32
)
ENGINE = MergeTree()
ORDER BY (unit_node_uuid, create_datetime)
PRIMARY KEY (unit_node_uuid, create_datetime)
TTL expiration_datetime
SETTINGS
    merge_with_ttl_timeout = 600,
    index_granularity = 128;

INSERT INTO window_entry_new
SELECT
    unit_node_uuid,
    state,
    state_type,
    create_datetime,
    expiration_datetime,
    size
FROM window_entry;

RENAME TABLE window_entry TO window_entry_old, window_entry_new TO window_entry;

DROP TABLE window_entry_old;


CREATE TABLE aggregation_entry_new
(
    unit_node_uuid UUID,
    state Float64,
    aggregation_type Enum8('Avg' = 1, 'Min' = 2, 'Max' = 3, 'Sum' = 4),
    time_window_size UInt32,
    create_datetime DateTime64(3),
    start_window_datetime DateTime64(3),
    end_window_datetime DateTime64(3)
)
ENGINE = MergeTree()
ORDER BY (unit_node_uuid, start_window_datetime)
PRIMARY KEY (unit_node_uuid, start_window_datetime)
SETTINGS
    index_granularity = 128;

INSERT INTO aggregation_entry_new
SELECT
    unit_node_uuid,
    state,
    aggregation_type,
    time_window_size,
    create_datetime,
    start_window_datetime,
    end_window_datetime
FROM aggregation_entry;

RENAME TABLE aggregation_entry TO aggregation_entry_old, aggregation_entry_new TO aggregation_entry;

DROP TABLE aggregation_entry_old;



