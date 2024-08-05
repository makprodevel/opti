import asyncio
from typing import AsyncGenerator
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from opti.core import config
config.DB_NAME = 'test_opti'
config.REDIS_DB = 2

from opti.core.database import DBase, engine
from opti.core.redis import init_redis_pool, shutdown_redis_pool
from opti.main import app


@pytest.fixture(autouse=True, scope='session')
async def prepare_database():
    metadata = DBase.metadata
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)


@pytest.fixture(autouse=True, scope='session')
async def setup_redis():
    await init_redis_pool()
    yield
    await shutdown_redis_pool()


@pytest.fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


client = TestClient(app)


@pytest.fixture(scope='session')
async def ac() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
