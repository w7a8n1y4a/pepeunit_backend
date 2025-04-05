CREATE TABLE device_logs
(
    log_uuid UUID,
    level Enum8('debug' = 1, 'info' = 2, 'warning' = 3, 'error' = 4, 'critical' = 5),
    unit_uuid UUID,
    log_text String,
    log_time DateTime,
    expiration_time DateTime MATERIALIZED log_time + INTERVAL 24 HOUR
)
ENGINE = MergeTree()
ORDER BY (unit_uuid, log_time)
TTL expiration_time
SETTINGS merge_with_ttl_timeout = 600;