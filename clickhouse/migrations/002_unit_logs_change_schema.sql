CREATE TABLE unit_logs_new
(
    uuid UUID,
    level Enum8('Debug' = 1, 'Info' = 2, 'Warning' = 3, 'Error' = 4, 'Critical' = 5),
    unit_uuid UUID,
    text String,
    create_datetime DateTime64(3),
    expiration_datetime DateTime
)
ENGINE = MergeTree()
ORDER BY (unit_uuid, create_datetime)
TTL expiration_datetime
SETTINGS merge_with_ttl_timeout = 600;

INSERT INTO unit_logs_new
SELECT
    uuid,
    level,
    unit_uuid,
    text,
    toDateTime64(create_datetime, 3),
    toDateTime64(create_datetime, 3)
FROM unit_logs;

RENAME TABLE unit_logs TO unit_logs_old, unit_logs_new TO unit_logs;

DROP TABLE unit_logs_old;