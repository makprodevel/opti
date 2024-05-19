from fastapi import FastAPI
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth, OAuthError
from .config import GOOGLE_CLIENT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, SECRET_KEY

from .jwt_utils import create_token, CREDENTIALS_EXCEPTION, valid_email_from_db


auth_app = FastAPI()
auth_app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

oauth = OAuth()
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    client_kwargs={
        'scope': 'email profile openid',
        'redirect_url': GOOGLE_REDIRECT_URI
    }
)


@auth_app.get("/")
async def login(request: Request):
    url = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, url)


@auth_app.get('/google')
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        raise CREDENTIALS_EXCEPTION

    user = token.get('userinfo')
    email = user.get("email")

    if await valid_email_from_db(email):
        return {'result': True, 'access_token': create_token(email)}
    raise CREDENTIALS_EXCEPTION
