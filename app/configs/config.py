import string
import toml

from pydantic_settings import BaseSettings


with open("pyproject.toml", "r") as f:
    data = toml.loads(f.read())


class Settings(BaseSettings):
    """.env variables"""

    debug: bool
    test: bool = False
    app_prefix: str
    api_v1_prefix: str
    project_name: str = data['tool']['poetry']['name']
    version: str = data['tool']['poetry']['version']
    description: str = data['tool']['poetry']['description']
    authors: list = data['tool']['poetry']['authors']
    license: str = data['tool']['poetry']['license']

    backend_domain: str

    auth_token_expiration: str
    sqlalchemy_database_url: str

    secret_key: str
    encrypt_key: str
    static_salt: str
    telegram_token: str
    telegram_bot_link: str

    save_repo_path: str

    mqtt_host: str
    mqtt_port: int
    mqtt_keepalive: int
    mqtt_api_key: str
    mqtt_secret_key: str

    redis_url: str

    available_topic_symbols: str = string.ascii_lowercase + string.ascii_uppercase + '0123456789/_-'
    state_send_interval: int = 300
