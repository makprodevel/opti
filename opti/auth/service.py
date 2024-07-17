from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyCookie
from jose import JWTError
from starlette import status

from opti.auth.jwt import decode_token
from opti.core.redis import get_redis


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Could not validate credentials',
    headers={'WWW-Authenticate': 'Bearer'},
)


async def valid_user_from_db(user_id: UUID) -> bool:
    redis = get_redis()
    if await redis.sismember('valid_id', str(user_id)):
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
