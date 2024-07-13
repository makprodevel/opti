import uuid
from uuid import UUID
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select, func, and_, desc

from opti.api.schema import ClientActionType, MessageToClient, SendMessageSchema, ServerError, GetChatSchema, \
    MessageInChat, GetChatSchemaReturn, ReadedMessage, ChatPreview, StatusInit
from opti.core.database import async_session_maker
from opti.core.models import Message, User
from opti.core.redis import get_redis
from opti.core.config import logger
from opti.auth.auth import get_current_user_id, valid_user_from_db
from opti.core.utils import utc_now


chat = APIRouter(
    prefix='/chat',
    tags=['chat'],
)


class WebsocketError(Exception):
    ...


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
    msg_to_client = MessageToClient(
        message_id=message_id,
        sender_id=user_id,
        message=send_msg_input.message,
        message_time=utc_now()
    )
    new_message = Message(
        id=message_id,
        sender_id=user_id,
        recipient_id=send_msg_input.recipient_id,
        message=send_msg_input.message
    )
    db_session.add(new_message)
    await asyncio.gather(
        redis.publish(channel=str(send_msg_input.recipient_id), message=msg_to_client.model_dump_json()),
        websocket.send_json(msg_to_client.model_dump_json()),
        db_session.commit()
    )


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
    get_chat_return = GetChatSchemaReturn(messages=[
        MessageInChat(
            message_id=msg.id,
            message=msg.message,
            message_time=msg.created_at
        ) for msg in messages
    ])
    await websocket.send_json(get_chat_return.model_dump_json())


async def status_init(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_id: UUID,
):
    latest_messages = (
        select(
            Message.sender_id,
            Message.recipient_id,
            Message.message,
            Message.created_at,
            Message.is_viewed,
            func.row_number().over(partition_by=Message.sender_id, order_by=desc(Message.created_at)).label('rn')
        )
        .where(Message.recipient_id == user_id)
        .cte('latest_messages')
    )

    query = (
        select(User.id, User.nickname, latest_messages.c.message,
               latest_messages.c.created_at, latest_messages.c.is_viewed)
        .join(latest_messages, User.id == latest_messages.c.sender_id)
        .where(latest_messages.c.rn == 1)
        .order_by(desc(latest_messages.c.created_at))
    )

    result = await db_session.execute(query)
    chats_preview = StatusInit(chat_list=(ChatPreview(
        user_id=i[0],
        user_nickname=i[1],
        message=i[2],
        last_message_time=i[3],
        is_viewed=i[4],
        ) for i in result.all()))
    await websocket.send_json(chats_preview.model_dump_json())


async def readed_message(
    websocket: WebSocket,
    db_session: AsyncSession,
    input_: dict,
    user_id: UUID,
):
    try:
        readed_message_ = ReadedMessage.model_validate(input_)
    except KeyError as e:
        raise WebsocketError(e)
    query = update(Message).values(is_viewed=True).where(and_(Message.id==readed_message_.id, Message.recipient_id==user_id))
    await db_session.execute(query)
    await db_session.commit()


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
                    case ClientActionType.status_init:
                        await status_init(websocket, db_session, user_id)

            except (WebsocketError, json.decoder.JSONDecodeError, ValueError) as e:
                await websocket.send_json({'error': 'invalid json'})
                logger.warning(f'websocket error: {e}')
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
                    data = msg.get("data")
                    msg_in_redis = MessageToClient.model_validate_json(data)
                    await websocket.send_json(msg_in_redis.model_dump_json())
                    # query = update(Message).values(is_viewed=True).where(Message.id == msg_in_redis.message_id)
                    # await db_session.execute(query)
                    # await db_session.commit()


@chat.websocket('/ws')
async def chat_websocket(
    websocket: WebSocket,
):
    user_id: UUID = await get_current_user_id(token=websocket.cookies.get('jwt'))
    await websocket.accept()
    logger.debug(f"Open websocket for {user_id}")

    try:
        await asyncio.gather(
            chat_input_handler(websocket, user_id),
            chat_output_handler(websocket, user_id),
        )
    except WebSocketDisconnect:
        logger.debug(f"Websocket close for {user_id}")
