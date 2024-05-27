import uuid
from uuid import UUID
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select

from opti.api.schema import ClientActionType, MessageToClient, SendMessageSchema, ServerError, GetChatSchema, \
    MessageInChat, GetChatReturnSchema
from opti.core.database import get_async_session, async_session_maker
from opti.core.models import Message
from opti.core.redis import get_redis
from opti.core.config import logger
from opti.auth.auth import get_current_user_id, valid_user_from_db
from opti.core.utils import utc_now


chat = APIRouter(
    prefix='/chat',
    tags=['chat'],
)


class WebsocketError(Exception):
    def __init__(self, message):
        ...
        self.message = message


async def send_message(
    websocket: WebSocket,
    db_session: AsyncSession,
    input_: dict,
    user_id: UUID,
):
    redis = await get_redis()
    try:
        send_msg_input: SendMessageSchema = SendMessageSchema.model_validate(input_)
    except ValidationError as e:
        raise WebsocketError(e)
    if not await valid_user_from_db(send_msg_input.recipient_id):
        raise WebsocketError(f'invalid recipient_id: {send_msg_input.recipient_id}')

    message_id = uuid.uuid4()
    msg_in_redis = MessageToClient(
        message_id=message_id,
        sender_id=user_id,
        message=send_msg_input.message,
        message_time=utc_now()
    )
    await redis.publish(channel=str(send_msg_input.recipient_id), message=msg_in_redis.model_dump_json())
    new_message = Message(
        id=message_id,
        sender_id=user_id,
        recipient_id=send_msg_input.recipient_id,
        message=send_msg_input.message
    )
    db_session.add(new_message)
    await db_session.commit()


async def get_chat(
    websocket: WebSocket,
    db_session: AsyncSession,
    input_: dict,
    user_id: UUID,
):
    try:
        get_chat_ = GetChatSchema.model_validate(input_)
    except KeyError as e:
        raise WebsocketError(e)
    if not await valid_user_from_db(get_chat_.recipient_id):
        raise WebsocketError(f'invalid recipient_id: {get_chat_.recipient_id}')

    query = select(Message).where(Message.recipient_id==get_chat_.recipient_id and Message.sender_id==user_id)
    result = await db_session.execute(query)
    messages: list[Message] = result.scalars().all()
    get_chat_return = GetChatReturnSchema(messages=[
        MessageInChat(
            message_id=msg.id,
            message=msg.message,
            message_time=msg.created_at
        ) for msg in messages
    ])
    await websocket.send_json(get_chat_return.model_dump_json())


async def chat_input_handler(
    websocket: WebSocket,
    user_id: UUID,
):
    async with async_session_maker() as db_session:
        while True:
            try:
                input_: dict = await websocket.receive_json()
                action_type = input_.get('action_type')
                match ClientActionType(action_type):
                    case ClientActionType.send_message:
                        await send_message(websocket, db_session, input_, user_id)
                    case ClientActionType.get_chat:
                        await get_chat(websocket, db_session, input_, user_id)

            except (WebsocketError, json.decoder.JSONDecodeError, ValueError) as e:
                await websocket.send_json({'error': 'invalid json'})
                logger.warning(f'error validation: {e}')
                continue


async def chat_output_handler(
    websocket: WebSocket,
    user_id: UUID,
):
    async with async_session_maker() as db_session:
        redis = await get_redis()
        async with redis.pubsub() as subscribe:
            await subscribe.psubscribe(str(user_id))
            while True:
                msg = await subscribe.get_message(ignore_subscribe_messages=True)
                if msg is not None:
                    logger.debug(f'data to handler from redis: {msg}')
                    data = msg.get("data")
                    msg_in_redis = MessageToClient.model_validate_json(data)

                    msg_to_client = MessageToClient(
                        message_id=msg_in_redis.message_id,
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
):
    user_id: UUID = await get_current_user_id(token=websocket.cookies.get('jwt'))
    await websocket.accept()
    logger.info(f"Open websocket for {user_id}")

    try:
        await asyncio.gather(
            chat_input_handler(websocket, user_id),
            chat_output_handler(websocket, user_id),
        )
    except WebSocketDisconnect:
        logger.info(f"Websocket close for {user_id}")
