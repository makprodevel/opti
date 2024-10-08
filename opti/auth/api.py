from uuid import UUID

import aiohttp
from fastapi import APIRouter, Depends, Response, HTTPException, Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from sqlalchemy import select
from starlette import status

from opti.auth.scheme import FetchGoogleClientId
from opti.core.database import async_session_maker
from opti.auth.jwt import create_token, decode_google_token
from opti.auth.models import User
from opti.core.redis import get_redis
from opti.core.utils import create_nickname_from_email
from opti.core.config import logger, GOOGLE_CLIENT_ID

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


async def get_id_from_email(email: str) -> UUID:
    async with async_session_maker() as session:
        query = select(User).where(User.email == email)
        user = await session.execute(query)
        user: User = user.scalar()
        if user is not None and user.is_blocked:
            logger.info(f'User {user.id} trying pass.')
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='User has been blocked'
            )
        if user is None:
            new_user = User(
                email=email,
                nickname=create_nickname_from_email(email),
            )
            session.add(new_user)
            await session.commit()
            user = new_user
        return user.id


@auth.get('/googleclientid', response_model=FetchGoogleClientId)
async def fetch_google_client_id():
    return FetchGoogleClientId(GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID)


@auth.get('/google')
async def get_google_code(
    response: Response,
    token: str = Depends(oauth2_scheme),
):
    user_info = await decode_google_token(token)
    email = user_info.get('email')
    user_id = await get_id_from_email(email)
    redis = get_redis()
    await redis.sadd('valid_id', str(user_id))
    response.set_cookie('jwt', create_token(str(user_id)), secure=True, httponly=True, samesite=None)
    logger.debug(f"get google token for {user_id}")


@auth.get('/set_token_in_cookie')
async def set_token_in_cookie(
    response: Response,
    request: Request,
    token: str = Depends(oauth2_scheme),
):
    """
    only for docs and tests
    """
    if request.url.path == "/docs-only-endpoint":
        raise HTTPException(status_code=403, detail="Forbidden")

    async with aiohttp.ClientSession() as session:
        async with session.get('https://www.googleapis.com/oauth2/v3/userinfo',
                               headers={'Authorization': f'Bearer {token}'}) as http_response:
            http_response.raise_for_status()
            user_info = await http_response.json()

    email = user_info.get('email')
    user_id = await get_id_from_email(email)
    redis = get_redis()
    await redis.sadd('valid_id', str(user_id))
    token = create_token(str(user_id))
    response.set_cookie('jwt', token, secure=True, httponly=True)
    logger.debug(f"get token for {email}")
    return {"token": token}
