from dotenv import load_dotenv
import os
from loguru import logger

if 'RELEASE' not in os.environ:
    load_dotenv()

logger.add('logs/log.txt', rotation="500 KB")
origins = [
    'http://localhost:5173/',
    'http://localhost:8000/',
    'http://localhost/',
    'https://opti-app.serveo.net',
]
GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_CERTS_TTL = 60
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
SECRET_KEY = os.environ.get('SECRET_KEY')
DB_HOST = os.environ.get("POSTGRESQL_HOST")
DB_PORT = os.environ.get("POSTGRESQL_PORT", 5432)
DB_NAME = os.environ.get("POSTGRESQL_NAME", "opti")
DB_USER = os.environ.get("POSTGRESQL_USER", "postgres") 
DB_PASS = os.environ.get("POSTGRESQL_PASS")
API_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
REDIS_DB = os.environ.get("REDIS_DB", 0)
CELERY_BROKER = os.environ.get("CELERY_BROKER", REDIS_URL)
