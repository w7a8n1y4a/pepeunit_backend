from dotenv import load_dotenv
import os
from os.path import join, dirname

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


class BaseConfig:
    DEBUG = bool(os.environ.get('DEBUG', False))
    SECRET_KEY = os.environ.get('SECRET_KEY', 'secret-key-goes-here')
    NEO4J_DATABASE_URI = os.environ.get(
        'NEO4J_DATABASE_URI', 'bolt://neo4j:1234@127.0.0.1:7687'
    )


settings = BaseConfig()
