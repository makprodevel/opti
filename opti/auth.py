import requests
from fastapi import APIRouter, Depends, Response, HTTPException, Body, Header
from fastapi.security import OAuth2AuthorizationCodeBearer, APIKeyCookie
from jose.jwt import JWTError
from sqlalchemy import select
from starlette import status

from .database import async_session_maker
from .jwt import create_token, decode_token, create_refresh_token
from .models import User
from .utils import create_nickname_from_email


auth = APIRouter(
    prefix='/auth',
    tags=['auth']
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
    tokenUrl="https://oauth2.googleapis.com/token",
    scopes={
        "openid": "OpenID connect to authenticate users",
        "https://www.googleapis.com/auth/userinfo.email": "Access to user's email address",
        "https://www.googleapis.com/auth/userinfo.profile": "Access to user's profile information",
    },
)

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Could not validate credentials',
    headers={'WWW-Authenticate': 'Bearer'},
)


async def valid_email_from_db(email) -> bool:
    async with async_session_maker() as session:
        if not await session.get(User, email):
            new_user = User(
                email=email,
                nickname=create_nickname_from_email(email),
            )
            await session.add(new_user)
        query = select(User).where(User.email == email)
        user = await session.execute(query)
        user: User = user.scalar()
        await session.commit()
        return not user.is_blocked


async def get_current_user_email(token: str = Depends(APIKeyCookie(name='jwt'))):
    try:
        payload = decode_token(token)
        email: str = payload.get('sub')
        if email is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    if await valid_email_from_db(email):
        return email

    raise CREDENTIALS_EXCEPTION


@auth.get('/get-token')
async def get_token(
        response: Response,
        token: str = Depends(oauth2_scheme),
):
    user_info = requests.get('https://www.googleapis.com/oauth2/v3/userinfo',
                             headers={'Authorization': f'Bearer {token}'})
    email = user_info.json().get('email')
    if await valid_email_from_db(email):
        response.set_cookie('jwt', create_token(email), secure=True, httponly=True)
        return create_refresh_token(email)

    raise CREDENTIALS_EXCEPTION


@auth.get('/refresh-token')
async def refresh_token(
        response: Response,
        refresh_token: str = Header()
):
    try:
        payload = decode_token(refresh_token)
        email: str = payload.get('sub')
        if email is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    if await valid_email_from_db(email):
        response.set_cookie('jwt', create_token(email), secure=True, httponly=True)
        return create_refresh_token(email)

    raise CREDENTIALS_EXCEPTION
