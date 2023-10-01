from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """ .env variables """

    debug: bool
    secret_key: str
    neo4j_database_url: str
