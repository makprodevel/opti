import asyncio

from conftest import client, async_session_maker
from sqlalchemy import select, insert
from opti.models import User
from opti.utils import create_nickname_from_email


async def test_add_user():
    async with async_session_maker() as session:
        email = "test@gmail.com"
        query = insert(User).values(email=email, nickname=create_nickname_from_email(email))
        await session.execute(query)
        await session.commit()
        assert True