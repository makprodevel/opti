from uuid import UUID
import requests
from fastapi import APIRouter, Depends, Response, HTTPException, Header
from fastapi.security import OAuth2AuthorizationCodeBearer, APIKeyCookie
from jose.jwt import JWTError
from redis import Redis
from sqlalchemy import select
from starlette import status

from opti.core.database import async_session_maker
from opti.core.redis import get_redis
from opti.auth.jwt import create_token, decode_token, create_refresh_token, decode_google_token
from opti.core.models import User
from opti.core.utils import create_nickname_from_email
from opti.core.config import logger


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


async def get_id_from_email(email: str) -> UUID:
    async with async_session_maker() as session:
        query = select(User).where(User.email == email)
        user = await session.execute(query)
        user: User = user.scalar()
        if user is None:
            new_user = User(
                email=email,
                nickname=create_nickname_from_email(email),
            )
            session.add(new_user)
            await session.commit()
            user: User = new_user
        if user.is_blocked:
            logger.info(f'User {user.id} trying pass.')
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='User has been blocked'
            )
        return user.id


async def valid_user_from_db(user_id: UUID) -> bool:
    redis = get_redis()
    if await redis.sismember('valid_id', str(user_id)):
        return True
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if user is not None and not user.is_blocked:
            await redis.sadd('valid_id', str(user_id))
            return True


async def get_current_user_id(
        token: str = Depends(APIKeyCookie(name='jwt'))
) -> UUID:
    try:
        payload = decode_token(token)
        user_id: str = payload.get('sub')
        if user_id is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    user_id: UUID = UUID(user_id)

    if await valid_user_from_db(user_id):
        return user_id

    raise CREDENTIALS_EXCEPTION


@auth.get('/google')
async def get_google_code(
    response: Response,
    token: str = Depends(oauth2_scheme),
):
    logger.debug(token)
    user_info = decode_google_token(token)
    email = user_info.get('email')
    user_id = await get_id_from_email(email)
    response.set_cookie('jwt', create_token(str(user_id)), secure=True, httponly=True)
    logger.debug(f"get google token for {email}")
    return create_refresh_token(str(user_id))


@auth.get('/get-token')
async def get_token(
        response: Response,
        token: str = Depends(oauth2_scheme),
):
    user_info = requests.get('https://www.googleapis.com/oauth2/v3/userinfo',
                             headers={'Authorization': f'Bearer {token}'})
    email = user_info.json().get('email')
    user_id = await get_id_from_email(email)
    response.set_cookie('jwt', create_token(str(user_id)), secure=True, httponly=True)
    logger.debug(f"get token for {email}")
    return create_refresh_token(str(user_id))


@auth.get('/refresh-token')
async def refresh_token(
        response: Response,
        refresh_token: str = Header()
):
    try:
        payload = decode_token(refresh_token)
        user_id: str = payload.get('sub')
        if user_id is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    if await valid_user_from_db(UUID(user_id)):
        response.set_cookie('jwt', create_token(user_id), secure=True, httponly=True)
        logger.debug(f"refresh token for {user_id}")
        return create_refresh_token(user_id)

    raise CREDENTIALS_EXCEPTION
