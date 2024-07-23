import string
import toml

from pydantic_settings import BaseSettings


with open("pyproject.toml", "r") as f:
    data = toml.loads(f.read())


class Settings(BaseSettings):
    """.env variables"""

    debug: bool
    app_prefix: str
    api_v1_prefix: str
    project_name: str = data['tool']['poetry']['name']
    version: str = data['tool']['poetry']['version']
    description: str = data['tool']['poetry']['description']
    authors: list = data['tool']['poetry']['authors']
    license: str = data['tool']['poetry']['license']

    backend_domain: str
    secure: bool = True
    http_type: str = 'https'

    backend_link: str = ''
    backend_link_prefix: str = ''
    backend_link_prefix_and_v1: str = ''

    auth_token_expiration: str
    sqlalchemy_database_url: str

    secret_key: str
    encrypt_key: str
    static_salt: str
    telegram_token: str
    telegram_bot_link: str

    save_repo_path: str

    mqtt_host: str
    mqtt_secure: bool = True
    mqtt_http_type: str = 'https'
    mqtt_port: int
    mqtt_api_port: int = 18083
    mqtt_keepalive: int
    mqtt_api_key: str
    mqtt_secret_key: str

    redis_url: str

    available_topic_symbols: str = string.ascii_lowercase + string.ascii_uppercase + string.digits + '/_-'
    state_send_interval: int = 300

    test_clear_data: bool = True
    test_private_repo_json: str = ''
