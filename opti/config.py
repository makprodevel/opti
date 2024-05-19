import os
from dotenv import load_dotenv


load_dotenv()

GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google"

GOOGLE_CLIENT_ID = os.environ.get('client-id')
GOOGLE_CLIENT_SECRET = os.environ.get('client-secret')
SECRET_KEY = os.environ.get('secret-key')
DB_HOST = os.environ.get("db_host")
DB_PORT = os.environ.get("db_port")
DB_NAME = os.environ.get("db_name")
DB_USER = os.environ.get("db_user")
DB_PASS = os.environ.get("db_pass")