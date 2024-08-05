from sqlalchemy import select

from opti.auth.jwt import create_token
from opti.auth.models import User
from opti.core.database import async_session_maker
from tests.conftest import client
from tests.test_auth import email


async def test_ws():
    async with async_session_maker() as session:
        query = select(User).where(User.email == email)
        result = await session.execute(query)
        user = result.scalar()
        token = create_token(str(user.id))
        with client.websocket_connect("/ws", cookies={"jwt": token}) as websocket:
            data = websocket.receive_json()
            assert data == {"msg": "Hello WebSocket"}