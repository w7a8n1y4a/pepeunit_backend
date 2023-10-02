from dotenv import load_dotenv
from neomodel import config

from app.core.config import Settings

load_dotenv()

settings = Settings()

config.DATABASE_URL = settings.neo4j_database_url
