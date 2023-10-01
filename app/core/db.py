from neomodel import config

from app import settings


config.DATABASE_URL = settings.neo4j_database_url
