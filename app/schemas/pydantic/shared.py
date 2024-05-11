from pydantic import BaseModel

from app import settings


link_to_backend = f'https://{settings.backend_domain}{settings.app_prefix}'


class Root(BaseModel):
    name: str = settings.project_name
    version: str = settings.version
    description: str = settings.description
    license: str = settings.license
    authors: list = settings.authors
    swagger: str = f'{link_to_backend}/docs'
    graphql: str = f'{link_to_backend}/graphql'
    telegram_bot: str = settings.telegram_bot_link
