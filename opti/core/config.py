from dotenv import load_dotenv
load_dotenv()

import os
from loguru import logger


logger.add('logs/log.txt', rotation="500 KB")


GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google"

GOOGLE_CLIENT_ID = os.environ.get('client-id')
GOOGLE_CLIENT_SECRET = os.environ.get('client-secret')
SECRET_KEY = os.environ.get('secret-key')
DB_HOST = os.environ.get("db_host")
DB_PORT = os.environ.get("db_port")
DB_NAME = os.environ.get("db_name")
DB_USER = os.environ.get("db_user")
DB_PASS = os.environ.get("db_pass")
API_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30
REDIS_URL = os.environ.get("redis_url", "redis://localhost:6379")
REDIS_DB = os.environ.get("redis_db", 0)
