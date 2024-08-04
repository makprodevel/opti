from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from opti.auth.api import auth
from opti.api.user_api import user_api
from opti.chat.api import chat
from opti.core.config import logger, origins
from opti.core.redis import init_redis_pool, shutdown_redis_pool, get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis_pool()
    logger.info("Opti is up")
    yield
    await shutdown_redis_pool()
    logger.info("Opti is down")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth)
app.include_router(user_api)
app.include_router(chat)


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
