from fastapi import APIRouter, Depends, Body
from sqlalchemy import update, text
from sqlalchemy.exc import SQLAlchemyError

from opti.api.schema import CurrentUser, ChangeNickname, SearchResult, UserInfo
from opti.auth.service import get_current_user_id, CREDENTIALS_EXCEPTION
from opti.core.database import get_async_session, AsyncSession
from opti.auth.models import User
from opti.core.config import logger


user_api = APIRouter(
    prefix='/api',
    tags=['api']
)


@user_api.get('/me', response_model=CurrentUser)
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session)
) -> CurrentUser:
    logger.debug(f'get me for {user_id}')
    user = await session.get(User, user_id)
    return CurrentUser(email=user.email, nickname=user.nickname)


@user_api.put('/me', response_model=ChangeNickname)
async def change_nickname(
    data: ChangeNickname = Body(...),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        query = update(User).values(nickname=data.new_nickname).where(User.id == user_id)
        await session.execute(query)
        await session.commit()
        return data
    except SQLAlchemyError as e:
        logger.error('change nickname error:', e)
        await session.rollback()
        raise CREDENTIALS_EXCEPTION


@user_api.post('/search/user', response_model=SearchResult)
async def search_user(
    q: str,
    session: AsyncSession = Depends(get_async_session)
):
    logger.info(f'search user: {q}')
    query = text("""
            SELECT users.id, users.nickname FROM users
            WHERE nickname % :search_term
        """)
    result = await session.execute(query, {'search_term': q})
    users = SearchResult(users=[UserInfo(id=i.id, nickname=i.nickname) for i in result])
    return users
