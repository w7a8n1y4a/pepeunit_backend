from dotenv import load_dotenv

from app.configs.config import Settings
from app.dto.enum import AgentType

load_dotenv()

settings = Settings()
settings.backend_http_type = 'https' if settings.backend_secure else 'http'
settings.mqtt_http_type = 'https' if settings.mqtt_secure else 'http'

settings.backend_link = f'{settings.backend_http_type}://{settings.backend_domain}'
settings.backend_link_prefix = settings.backend_link + settings.backend_app_prefix
settings.backend_link_prefix_and_v1 = settings.backend_link_prefix + settings.backend_api_v1_prefix
