from httpx import AsyncClient
from sqlalchemy import select

from opti.auth.jwt import create_token
from opti.auth.models import User
from opti.core.database import async_session_maker
from tests.test_auth import email


async def test_get_current_user(ac: AsyncClient):
    async with async_session_maker() as session:
        query = select(User).where(User.email == email)
        result = await session.execute(query)
        user = result.scalar()
        token = create_token(str(user.id))

        response = await ac.get("/api/me", cookies={"jwt": token})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["nickname"] == user.nickname


async def test_change_nickname(ac: AsyncClient):
    async with async_session_maker() as session:
        query = select(User).where(User.email == email)
        result = await session.execute(query)
        user = result.scalar()
        token = create_token(str(user.id))
        new_nickname = "new_nickname"

        response = await ac.put("/api/me", cookies={"jwt": token}, json={
            'new_nickname': new_nickname
        })
        assert response.status_code == 200
        assert new_nickname == response.json()['new_nickname']
