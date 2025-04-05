CREATE TABLE unit_logs
(
    uuid UUID,
    level Enum8('Debug' = 1, 'Info' = 2, 'Warning' = 3, 'Error' = 4, 'Critical' = 5),
    unit_uuid UUID,
    text String,
    create_datetime DateTime,
    expiration_datetime DateTime MATERIALIZED create_datetime + INTERVAL 24 HOUR
)
ENGINE = MergeTree()
ORDER BY (unit_uuid, create_datetime)
TTL expiration_datetime
SETTINGS merge_with_ttl_timeout = 600;