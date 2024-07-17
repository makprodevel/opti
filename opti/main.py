from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from starlette.middleware.cors import CORSMiddleware

from opti.auth.auth import auth
from opti.api.user_api import user_api
from opti.core.config import logger, origins
from opti.core.redis import init_redis_pool, shutdown_redis_pool, get_redis

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth)
app.include_router(user_api)


@app.on_event("startup")
async def startup():
    await init_redis_pool()
    FastAPICache.init(RedisBackend(get_redis()), prefix="fastapi-cache")
    logger.info("Opti is up")


@app.on_event("shutdown")
async def shutdown_event():
    await shutdown_redis_pool()
    logger.info("Opti is down")


@app.exception_handler(Exception)
async def exception_handler(exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
