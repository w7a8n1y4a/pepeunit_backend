from datetime import timedelta, datetime

import jwt
from dotenv import load_dotenv

from app.configs.config import Settings

load_dotenv()

settings = Settings()
settings.http_type = 'https' if settings.secure else 'http'
settings.mqtt_http_type = 'https' if settings.mqtt_secure else 'http'

settings.backend_link = f'{settings.http_type}://{settings.backend_domain}'
settings.backend_link_prefix = settings.backend_link + settings.app_prefix
settings.backend_link_prefix_and_v1 = settings.backend_link_prefix + settings.api_v1_prefix

access_token_exp = datetime.utcnow() + timedelta(seconds=settings.auth_token_expiration)

jwt_token = jwt.encode(
    {'domain': settings.backend_domain, 'exp': access_token_exp},
    settings.secret_key,
    'HS256',
)

settings.backend_token = jwt_token
