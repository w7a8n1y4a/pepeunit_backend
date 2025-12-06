import string

import toml
from pydantic_settings import BaseSettings

with open("pyproject.toml") as f:
    data = toml.loads(f.read())


class Settings(BaseSettings):
    project_name: str = data["project"]["name"]
    version: str = data["project"]["version"]
    description: str = data["project"]["description"]
    authors: list = data["project"]["authors"]
    license: str = data["project"]["license"]["text"]

    pu_ff_telegram_bot_enable: bool = True
    pu_ff_grafana_integration_enable: bool = True
    pu_ff_datapipe_enable: bool = True
    pu_ff_datapipe_default_last_value_enable: bool = True
    pu_ff_prometheus_enable: bool = True

    pu_log_format: str = "json"
    pu_min_log_level: str = "INFO"

    pu_app_prefix: str = "/pepeunit"
    pu_api_v1_prefix: str = "/api/v1"

    pu_worker_count: int = 2

    pu_domain: str
    pu_secure: bool = True

    pu_auth_token_expiration: int = 2678400
    pu_save_repo_path: str = "repo_cache"

    pu_sqlalchemy_database_url: str
    pu_clickhouse_database_url: str

    pu_secret_key: str
    pu_encrypt_key: str
    pu_static_salt: str

    pu_min_interval_sync_repository: int = 10

    pu_state_send_interval: int = 60
    pu_max_external_repo_size: int = 50
    pu_max_cipher_length: int = 1_000_000

    pu_min_topic_update_time: int = 30
    pu_unit_log_expiration: int = 86400

    pu_max_pagination_size: int = 500

    pu_available_topic_symbols: str = (
        string.ascii_letters + string.digits + "/_-"
    )
    pu_available_name_entity_symbols: str = (
        string.ascii_letters + string.digits + "_-."
    )
    pu_available_password_symbols: str = (
        string.ascii_letters + string.digits + string.punctuation
    )

    pu_telegram_bot_mode: str = "webhook"
    pu_telegram_del_old_webhook: bool = True
    pu_telegram_token: str
    pu_telegram_bot_link: str
    pu_telegram_items_per_page: int = 7
    pu_telegram_header_entity_length: int = 15
    pu_telegram_git_hash_length: int = 8

    pu_prometheus_multiproc_dir: str = "./prometheus_metrics"

    pu_redis_url: str = "redis://redis:6379/0"

    pu_mqtt_host: str
    pu_mqtt_secure: bool = True
    pu_mqtt_port: int = 1883
    pu_mqtt_api_port: int = 18083
    pu_mqtt_keepalive: int = 60

    pu_mqtt_username: str
    pu_mqtt_password: str

    pu_mqtt_redis_auth_url: str = "redis://redis:6379/0"

    pu_mqtt_max_clients: int = 10000
    pu_mqtt_max_client_connection_rate: str = "20/s"
    pu_mqtt_max_client_id_len: int = 512

    pu_mqtt_client_max_messages_rate: str = "30/s"
    pu_mqtt_client_max_bytes_rate: str = "1MB/s"

    pu_mqtt_max_payload_size: int = 256
    pu_mqtt_max_qos: int = 2
    pu_mqtt_max_topic_levels: int = 5
    pu_mqtt_max_len_message_queue: int = 128
    pu_mqtt_max_topic_alias: int = 128

    pu_github_token_name: str = ""
    pu_github_token_pat: str = ""

    pu_grafana_admin_user: str = ""
    pu_grafana_admin_password: str = ""
    pu_grafana_limit_unit_node_per_one_panel: int = 10

    pu_test_integration_clear_data: bool = True
    pu_test_integration_private_repo_json: str = ""

    pu_test_load_mqtt_duration: int = 120
    pu_test_load_mqtt_unit_count: int = 100
    pu_test_load_mqtt_rps: int = 200
    pu_test_load_mqtt_value_type: str = "Text"
    pu_test_load_mqtt_duplicate_count: int = 10
    pu_test_load_mqtt_message_size: int = 15
    pu_test_load_mqtt_policy_type: str = "TimeWindow"
    pu_test_load_mqtt_workers: int = 10

    locust_headless: bool = True
    locust_users: int = 400
    locust_run_time: int = 120
    locust_spawn_rate: int = 10

    # calculated fields
    pu_http_type: str = "https"

    pu_link: str = ""
    pu_link_prefix: str = ""
    pu_link_prefix_and_v1: str = ""

    pu_mqtt_http_type: str = "https"

    pu_clickhouse_connection: None = None
    pu_time_window_sizes: None = None
