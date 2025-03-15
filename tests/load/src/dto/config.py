from dataclasses import dataclass


@dataclass
class LoadTestConfig:
    url: str
    duration: int
    unit_count: int
    rps: int
    duplicate_count: int
    message_size: int
    workers: int
    mqtt_admin: str
    mqtt_password: str
    test_hash: str
