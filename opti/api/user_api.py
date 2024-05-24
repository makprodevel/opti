from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from opti.auth.auth import get_current_user_email, CREDENTIALS_EXCEPTION
from opti.core.database import get_async_session, AsyncSession
from opti.core.models import User
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
        email: str = Depends(get_current_user_email),
        session: AsyncSession = Depends(get_async_session)
) -> CurrentUser:
    query = select(User).where(User.email == email)
    user = await session.execute(query)
    user = user.scalar()
    return CurrentUser(email=user.email, nickname=user.nickname)


@user_api.put('/me', response_model=CurrentUser)
async def change_nickname(
        new_nickname: str,
        email: str = Depends(get_current_user_email),
        session: AsyncSession = Depends(get_async_session)
) -> CurrentUser:
    try:
        query = update(User).values(nickname=new_nickname).where(User.email == email)
        await session.execute(query)
        await session.commit()
        return CurrentUser(email=email, nickname=new_nickname)
    except SQLAlchemyError as e:
        print('ошибка', e)
        await session.rollback()
        raise CREDENTIALS_EXCEPTION
