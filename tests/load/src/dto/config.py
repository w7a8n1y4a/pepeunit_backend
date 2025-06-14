from dataclasses import dataclass


@dataclass
class LoadTestConfig:
    url: str
    duration: int
    unit_count: int
    rps: int
    value_type: str
    duplicate_count: int
    message_size: int
    policy_type: str
    workers: int
    mqtt_admin: str
    mqtt_password: str
    test_hash: str
