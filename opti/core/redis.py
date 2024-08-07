from redis import asyncio as aioredis, Redis
from opti.core.config import REDIS_URL, REDIS_DB


redis: Redis = None


async def init_redis_pool():
    global redis
    redis = await aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        db=REDIS_DB,
        decode_responses=True,
    )


async def shutdown_redis_pool():
    global redis
    await redis.close()


def get_redis() -> Redis:
    global redis
    return redis