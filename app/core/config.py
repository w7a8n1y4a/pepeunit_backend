from pydantic import BaseSettings


class Settings(BaseSettings):
    debug: bool
    secret_key: str
    neo4j_database_uri: str
