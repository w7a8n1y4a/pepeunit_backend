import string

import toml
from pydantic_settings import BaseSettings

with open("pyproject.toml", "r") as f:
    data = toml.loads(f.read())


class Settings(BaseSettings):
    """.env variables"""

    project_name: str = data['tool']['poetry']['name']
    version: str = data['tool']['poetry']['version']
    description: str = data['tool']['poetry']['description']
    authors: list = data['tool']['poetry']['authors']
    license: str = data['tool']['poetry']['license']

    backend_debug: bool = False
    backend_app_prefix: str = '/pepeunit'
    backend_api_v1_prefix: str = '/api/v1'

    backend_worker_count: int = 2

    backend_domain: str
    backend_secure: bool = True

    backend_auth_token_expiration: int = 2678400
    backend_save_repo_path: str = 'repo_cache'

    sqlalchemy_database_url: str

    backend_secret_key: str
    backend_encrypt_key: str
    backend_static_salt: str

    backend_state_send_interval: int = 60
    backend_max_external_repo_size: int = 50
    backend_max_cipher_length: int = 1_000_000

    backend_min_topic_update_time: int = 30

    available_topic_symbols: str = string.ascii_letters + string.digits + '/_-'
    available_name_entity_symbols: str = string.ascii_letters + string.digits + '_-.'
    available_password_symbols: str = string.ascii_letters + string.digits + string.punctuation

    telegram_token: str
    telegram_bot_link: str

    redis_url: str = 'redis://redis:6379/0'

    mqtt_host: str
    mqtt_secure: bool = True
    mqtt_port: int = 1883
    mqtt_api_port: int = 18083
    mqtt_keepalive: int = 60

    mqtt_username: str
    mqtt_password: str

    mqtt_redis_auth_url: str = 'redis://redis:6379/0'

    mqtt_max_clients: int = 10000
    mqtt_max_client_connection_rate: str = '20/s'
    mqtt_max_client_id_len: int = 512

    mqtt_client_max_messages_rate: str = '30/s'
    mqtt_client_max_bytes_rate: str = '1MB/s'

    mqtt_max_payload_size: int = 256
    mqtt_max_qos: int = 2
    mqtt_max_topic_levels: int = 5
    mqtt_max_len_message_queue: int = 128
    mqtt_max_topic_alias: int = 128

    test_integration_clear_data: bool = False
    test_integration_private_repo_json: str = ''
    test_integration_run_backend: bool = False

    test_load_mqtt_duration: int = 120
    test_load_mqtt_unit_count: int = 40
    test_load_mqtt_rps: int = 100
    test_load_mqtt_duplicate_count: int = 10
    test_load_mqtt_message_size: int = 128
    test_load_mqtt_workers: int = 10

    locust_headless: bool = True
    locust_users: int = 400
    locust_run_time: int = 120
    locust_spawn_rate: int = 10

    # calculated fields
    backend_http_type: str = 'https'
    backend_token: str = ''

    backend_link: str = ''
    backend_link_prefix: str = ''
    backend_link_prefix_and_v1: str = ''

    mqtt_http_type: str = 'https'
