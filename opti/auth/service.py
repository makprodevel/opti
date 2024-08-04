from uuid import UUID

from aiocache import cached, Cache
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyCookie
from jose import JWTError
from starlette import status

from opti.auth.jwt import decode_token
from opti.auth.models import User
from opti.core.database import async_session_maker
from opti.core.redis import get_redis


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Could not validate credentials',
    headers={'WWW-Authenticate': 'Bearer'},
)


@cached(ttl=30, cache=Cache.REDIS, key='valid_user_cache')
async def valid_user_from_db(user_id: UUID) -> bool:
    async with async_session_maker() as session:
        user = await session.get(User, user_id)
        if user is not None and not user.is_blocked:
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
