from enum import Enum
from uuid import UUID
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from opti.core.database import get_async_session
from opti.core.models import Message
from opti.core.redis import get_redis
from redis import asyncio as aioredis
import asyncio
from opti.core.config import logger

from opti.auth.auth import get_current_user_id, valid_user_from_db

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


class ClientActionType(Enum):
    status_init = 'status_init'
    get_chat = 'get_chat'
    send_message = 'send_message'


async def send_message(
    websocket: WebSocket,
    db_session: AsyncSession,
    input_,
    user_id: UUID,
):
    redis = await get_redis()
    recipient_id = UUID(input_.get('recipient_id'))
    message = input_.get('message')
    if message is None:
        raise ValueError
    if not await valid_user_from_db(recipient_id):
        await websocket.send_json({'error': 'invalid recipient'})

    new_message = Message(
        sender_id=user_id,
        recipient_id=recipient_id,
        message=message
    )
    db_session.add(new_message)
    await redis.publish(channel=str(recipient_id), message=message)
    await db_session.commit()


async def get_chat(
        websocket: WebSocket,
        db_session: AsyncSession,
        input_,
        user_id: UUID,
):
    pass


async def chat_input_handler(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_id: UUID
):
    while True:
        try:
            input_ = await websocket.receive_json()
        except json.decoder.JSONDecodeError:
            await websocket.send_json({'error': 'invalid json'})
            continue
        action_type = input_.get('action_type')
        try:
            match ClientActionType(action_type):
                case ClientActionType.send_message:
                    await send_message(websocket, db_session, input_, user_id)
                case ClientActionType.get_chat:
                    await get_chat(websocket, db_session, input_, user_id)

        except ValueError:
            await websocket.send_json({'error': 'invalid argument'})


async def chat_output_handler(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_id: UUID
):
    redis = await get_redis()
    async with redis.pubsub() as subscribe:
        await subscribe.psubscribe(str(user_id))
        while True:
            msg = await subscribe.get_message(ignore_subscribe_messages=True)
            if msg is not None:
                logger.info(f'send: {msg.get("data")}')


@chat.websocket('/ws')
async def chat_websocket(
    websocket: WebSocket,
    db_session: AsyncSession = Depends(get_async_session)
):
    user_id = await get_current_user_id(token=websocket.cookies.get('jwt'))
    await websocket.accept()
    logger.info(f"Open websocket for {user_id}")

    try:
        await asyncio.gather(
            chat_input_handler(websocket, db_session, user_id),
            chat_output_handler(websocket, db_session, user_id),
        )
    except WebSocketDisconnect:
        logger.info(f"Websocket close for {user_id}")
