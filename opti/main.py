from fastapi import FastAPI, Request, APIRouter
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from opti.auth.api import auth
from opti.user_api.user_api import user_api
from opti.chat.api import chat
from opti.core.config import logger, origins
from opti.core.redis import init_redis_pool, shutdown_redis_pool


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_redis_pool()
    logger.info("Opti is up")
    yield
    await shutdown_redis_pool()
    logger.info("Opti is down")


app = FastAPI(lifespan=lifespan)
main_router = APIRouter(prefix="/api")


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@main_router.get('/')
async def is_run():
    return 'app is run'


main_router.include_router(auth)
main_router.include_router(user_api)
main_router.include_router(chat)
app.include_router(main_router)


@app.exception_handler(Exception)
async def exception_handler(_: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
