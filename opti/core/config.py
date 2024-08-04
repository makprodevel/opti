from dotenv import load_dotenv
import os
from loguru import logger


load_dotenv()

logger.add('logs/log.txt', rotation="500 KB")


origins = [
    'http://localhost:5173/',
    'http://localhost:8000/',
]

GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google"

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_CERTS_TTL = 60
GOOGLE_CLIENT_ID = os.environ.get('client_id')
GOOGLE_CLIENT_SECRET = os.environ.get('client_secret')
SECRET_KEY = os.environ.get('secret_key')
DB_HOST = os.environ.get("db_host")
DB_PORT = os.environ.get("db_port")
DB_NAME = os.environ.get("db_name")
DB_USER = os.environ.get("db_user")
DB_PASS = os.environ.get("db_pass")
API_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30
REDIS_URL = os.environ.get("redis_url", "redis://localhost:6379")
REDIS_DB = os.environ.get("redis_db", 0)
CELERY_BROKER = os.environ.get("celery_broker", REDIS_URL)