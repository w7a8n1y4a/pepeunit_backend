from pydantic import BaseSettings


class Settings(BaseSettings):
    """.env variables"""

    debug: bool
    app_prefix: str
    api_v1_prefix: str
    project_name: str
    version: str
    description: str

    secret_key: str
    auth_token_expiration: str
    sqlalchemy_database_url: str
