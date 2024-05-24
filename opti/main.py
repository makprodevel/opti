from fastapi import FastAPI
from .auth import auth
from .user_api import user_api
from .config import logger
from .redis import init_redis_pool, shutdown_redis_pool


app = FastAPI()
app.include_router(auth)
app.include_router(user_api)


@app.on_event("startup")
async def startup():
    await init_redis_pool()
    logger.info("Opti is up")


@app.on_event("shutdown")
async def shutdown_event():
    await shutdown_redis_pool()
    logger.info("Opti is down")

