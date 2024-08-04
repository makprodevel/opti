from opti.auth.service import valid_user_from_db
from opti.auth.models import User
from opti.core.database import async_session_maker
from opti.core.utils import create_nickname_from_email


async def test_valid_user_id():
    async with async_session_maker() as session:
        email = "test@gmail.com"
        new_user = User(
            email=email,
            nickname=create_nickname_from_email(email),
        )
        session.add(new_user)
        await session.commit()
        print(new_user.id)
        assert await valid_user_from_db(new_user.id)
