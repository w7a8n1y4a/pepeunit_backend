from pydantic import BaseModel

from app import settings


class Root(BaseModel):
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    authors: list = settings.authors
    swagger: str = f'{settings.backend_link_prefix}/docs'
    graphql: str = f'{settings.backend_link_prefix}/graphql'
    telegram_bot: str = settings.telegram_bot_link


class MqttRead(BaseModel):
    result: str
