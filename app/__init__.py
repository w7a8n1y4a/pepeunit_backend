from datetime import datetime, timedelta

import jwt
from dotenv import load_dotenv

from app.configs.config import Settings
from app.repositories.enum import AgentType

load_dotenv()

settings = Settings()
settings.backend_http_type = 'https' if settings.backend_secure else 'http'
settings.mqtt_http_type = 'https' if settings.mqtt_secure else 'http'

settings.backend_link = f'{settings.backend_http_type}://{settings.backend_domain}'
settings.backend_link_prefix = settings.backend_link + settings.backend_app_prefix
settings.backend_link_prefix_and_v1 = settings.backend_link_prefix + settings.backend_api_v1_prefix

access_token_exp = datetime.utcnow() + timedelta(seconds=settings.backend_auth_token_expiration)

jwt_token = jwt.encode(
    {'domain': settings.backend_domain, 'exp': access_token_exp, 'type': AgentType.BACKEND},
    settings.backend_secret_key,
    'HS256',
)

settings.backend_token = jwt_token
