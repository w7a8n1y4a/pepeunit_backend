import string

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """.env variables"""

    debug: bool
    app_prefix: str
    api_v1_prefix: str
    project_name: str
    version: str
    description: str

    backend_domain: str

    auth_token_expiration: str
    sqlalchemy_database_url: str

    secret_key: str
    encrypt_key: str
    static_salt: str
    telegram_token: str

    save_repo_path: str

    mqtt_host: str
    mqtt_port: int
    mqtt_keepalive: int
    mqtt_username: str
    mqtt_password: str

    redis_url: str

    available_topic_symbols: str = string.ascii_lowercase + string.ascii_uppercase + '0123456789/_-'
    state_send_interval: int = 300
