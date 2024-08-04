from typing import AsyncGenerator
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from opti.core.database import DBase, get_async_session
import opti.core.database as db
from opti.core.config import DB_HOST, DB_PASS, DB_PORT, DB_USER, REDIS_URL
from opti.core.redis import init_redis_pool, shutdown_redis_pool
from opti.main import app


DB_NAME_TEST = 'test_opti'
metadata = DBase.metadata
DATABASE_URL_TEST = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME_TEST}"
engine_test = create_async_engine(DATABASE_URL_TEST, poolclass=NullPool)
override_async_session_maker = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)
metadata.bind = engine_test


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with override_async_session_maker() as session:
        yield session


app.dependency_overrides[get_async_session] = override_get_async_session
db.async_session_maker = override_async_session_maker


@pytest.fixture(autouse=True, scope='session')
async def prepare_database():
    async with engine_test.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        await conn.run_sync(metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(metadata.drop_all)



client = TestClient(app)


@pytest.fixture(autouse=True, scope='session')
async def ac() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True, scope='session')
async def setup_redis():
    await init_redis_pool()
    yield
    await shutdown_redis_pool()
