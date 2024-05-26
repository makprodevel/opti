from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from opti.auth.auth import get_current_user_id, CREDENTIALS_EXCEPTION
from opti.core.database import get_async_session, AsyncSession
from opti.core.models import User
from opti.core.config import logger
from opti.api.chat import chat


user_api = APIRouter(
    prefix='/api',
    tags=['api']
)

user_api.include_router(chat)


class CurrentUser(BaseModel):
    email: str
    nickname: str


@user_api.get('/me', response_model=CurrentUser)
async def get_current_user(
        user_id: str = Depends(get_current_user_id),
        session: AsyncSession = Depends(get_async_session)
) -> CurrentUser:
    user = await session.get(User, user_id)
    return CurrentUser(email=user.email, nickname=user.nickname)


@user_api.put('/me')
async def change_nickname(
        new_nickname: str,
        user_id: str = Depends(get_current_user_id),
        session: AsyncSession = Depends(get_async_session)
):
    try:
        query = update(User).values(nickname=new_nickname).where(User.id == user_id)
        await session.execute(query)
        await session.commit()
        return new_nickname
    except SQLAlchemyError as e:
        logger.error('change nickname error:', e)
        await session.rollback()
        raise CREDENTIALS_EXCEPTION
