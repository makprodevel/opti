from enum import Enum
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
from pydantic import BaseModel
from opti.core.redis import get_redis
from redis import asyncio as aioredis
import asyncio
from opti.core.config import logger

from opti.auth.auth import get_current_user_email


chat = APIRouter(
    prefix='/chat',
    tags=['chat'],
)


class RowChat(BaseModel):
    email: str
    nickname: str
    last_message: str
    time_last_message: datetime
    is_read: bool


class ActionType(Enum):
    status_init = 'status_init'
    get_chat = 'get_chat'
    send_message = 'send_message'


async def chat_input_handler(websocket: WebSocket, redis: aioredis.Redis):
    while True:
        input = await websocket.receive_json()
        await redis.publish(channel='msg', message=input)
        print('input:', input)


async def chat_output_handler(websocket: WebSocket, redis: aioredis.Redis):
    async with redis.pubsub() as subscribe:
        await subscribe.psubscribe('msg')
        while True:
            msg = await subscribe.get_message(ignore_subscribe_messages=True)
            if msg is not None:
                msg = msg['data'].decode('utf-8')
                await websocket.send_text(msg)
                print('send:', msg)


@chat.websocket('/ws')
async def chat_websocket(
        websocket: WebSocket,
):
    email = await get_current_user_email(token=websocket.cookies.get('jwt'))
    await websocket.accept()
    redis = await get_redis()
    logger.info(f"Open websocket for: {email}")

    try:
        await asyncio.gather(
            chat_input_handler(websocket, redis),
            chat_output_handler(websocket, redis),
        )
    except WebSocketDisconnect:
        logger.info(f"Open close for: {email}")
