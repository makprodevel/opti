from uuid import UUID
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from opti.api.schema import ClientActionType, MessageInRedis, MessageToClient
from opti.core.database import get_async_session
from opti.core.models import Message
from opti.core.redis import get_redis
from opti.core.config import logger
from opti.auth.auth import get_current_user_id, valid_user_from_db


chat = APIRouter(
    prefix='/chat',
    tags=['chat'],
)


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
    await db_session.commit()
    msg_in_redis = MessageInRedis(
        message_id=new_message.id,
        sender_id=user_id,
        message=message,
        message_time=new_message.created_at
    )
    await redis.publish(channel=str(recipient_id), message=msg_in_redis.model_dump_json())


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
                logger.debug(f'data from redis to handler: {msg}')
                data = msg.get("data")
                msg_in_redis = MessageInRedis.model_validate_json(data)
                msg_to_client = MessageToClient(
                    sender_id=msg_in_redis.sender_id,
                    message=msg_in_redis.message,
                    message_time=msg_in_redis.message_time
                )
                await websocket.send_json(msg_to_client.model_dump_json())
                query = update(Message).values(is_viewed=True).where(Message.id == msg_in_redis.message_id)
                await db_session.execute(query)
                await db_session.commit()



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
