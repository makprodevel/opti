from sqlalchemy import select

from opti.auth.jwt import create_token
from opti.auth.service import valid_user_from_db, get_current_user_id
from opti.auth.models import User
from opti.core.database import async_session_maker
from opti.core.utils import create_nickname_from_email


email = "test_user@gmail.com"


async def test_valid_user_id():
    async with async_session_maker() as session:
        new_user = User(
            email=email,
            nickname=create_nickname_from_email(email),
        )
        session.add(new_user)
        await session.commit()
        assert await valid_user_from_db(new_user.id)


async def test_get_current_user_id():
    async with (async_session_maker() as session):
        query = select(User).where(User.email == email)
        result = await session.execute(query)
        user = result.scalar()
        token = create_token(str(user.id))
        assert user.id == await get_current_user_id(token)