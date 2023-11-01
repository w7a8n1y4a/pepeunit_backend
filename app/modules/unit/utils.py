from app.modules.unit.sql_models import Unit
from app import settings


def program_link_generation(unit: Unit):
    """ Генерирует ссылку для скачивания программы физического unit """

    return f'{settings.backend_domain}{settings.app_prefix}{settings.api_v1_prefix}/units/program/{unit.uuid}'
