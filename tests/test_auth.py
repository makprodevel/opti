from conftest import async_session_maker
from sqlalchemy import insert, select
from opti.auth.auth import valid_user_from_db
from opti.core.models import User
from opti.core.utils import create_nickname_from_email


async def test_valid_user_id():
    async with async_session_maker() as session:
        email = "test@gmail.com"
        query = insert(User).values(email=email, nickname=create_nickname_from_email(email))
        await session.execute(query)
        await session.commit()
        query = select(User).where(User.email == email)
        user = await session.execute(query)
        user: User = user.scalar()
        assert valid_user_from_db(user.id)