import string

import toml
from pydantic_settings import BaseSettings

with open("pyproject.toml", "r") as f:
    data = toml.loads(f.read())


class Settings(BaseSettings):
    """.env variables"""

    debug: bool = False
    app_prefix: str = '/pepeunit'
    api_v1_prefix: str = '/api/v1'
    project_name: str = data['tool']['poetry']['name']
    version: str = data['tool']['poetry']['version']
    description: str = data['tool']['poetry']['description']
    authors: list = data['tool']['poetry']['authors']
    license: str = data['tool']['poetry']['license']

    backend_domain: str
    secure: bool = True
    http_type: str = 'https'
    backend_token: str = ''

    backend_link: str = ''
    backend_link_prefix: str = ''
    backend_link_prefix_and_v1: str = ''

    auth_token_expiration: int = 2678400
    sqlalchemy_database_url: str

    secret_key: str
    encrypt_key: str
    static_salt: str
    telegram_token: str
    telegram_bot_link: str

    save_repo_path: str = 'repo_cache'

    mqtt_host: str
    mqtt_secure: bool = True
    mqtt_http_type: str = 'https'
    mqtt_port: int = 1883
    mqtt_api_port: int = 18083
    mqtt_keepalive: int = 60
    mqtt_username: str
    mqtt_password: str
    mqtt_max_payload_size: int = 50000

    redis_url: str = 'redis://redis:6379/0'
    redis_mqtt_auth_url: str = 'redis://redis:6379/0'

    available_topic_symbols: str = string.ascii_letters + string.digits + '/_-'
    available_name_entity_symbols: str = string.ascii_letters + string.digits + '_-.'
    available_password_symbols: str = string.ascii_letters + string.digits + string.punctuation
    state_send_interval: int = 60
    max_external_repo_size: int = 50
    max_cipher_length: int = 50000

    test_clear_data: bool = True
    test_private_repo_json: str = ''
