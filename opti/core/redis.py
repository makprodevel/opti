from redis import asyncio as aioredis
from opti.core.config import REDIS_URL, REDIS_DB


__redis = None

async def init_redis_pool():

    redis_c = await aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        db=REDIS_DB,
        decode_responses=True,
    )
    global __redis
    __redis = redis_c

async def shutdown_redis_pool():
    global __redis
    await __redis.close()


async def get_redis():
    global __redis
    return __redis