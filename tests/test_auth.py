from conftest import async_session_maker
from sqlalchemy import insert
from opti.core.models import User
from opti.core.utils import create_nickname_from_email


async def test_add_user():
    async with async_session_maker() as session:
        email = "test@gmail.com"
        query = insert(User).values(email=email, nickname=create_nickname_from_email(email))
        await session.execute(query)
        await session.commit()
        assert True