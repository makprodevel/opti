import uuid
from uuid import UUID
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, delete, or_

from opti.chat.schema import (
    SendMessageReturn,
    SendMessageSchema,
    GetChatSchema,
    MessageInChat,
    GetChatSchemaReturn,
    ChatPreview,
    GetPreviewReturn,
    ReadMessagesForRecipientReturn,
    ReadMessagesForSenderReturn,
    ServerActionType,
    DeleteChatScheme,
)
from opti.core.database import async_session_maker
from opti.auth.models import User
from opti.chat.models import Message
from opti.core.redis import get_redis
from opti.core.config import logger
from opti.auth.service import get_current_user_id, valid_user_from_db
from opti.core.utils import utc_now


chat = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


class WebsocketError(Exception): ...


async def send_message(
    websocket: WebSocket,
    db_session: AsyncSession,
    input_: dict,
    user_id: UUID,
):
    redis = get_redis()
    try:
        send_msg_input: SendMessageSchema = SendMessageSchema.model_validate(input_)
    except ValidationError as e:
        raise WebsocketError(e)
    if not await valid_user_from_db(send_msg_input.recipient_id):
        raise WebsocketError(f"invalid recipient_id: {send_msg_input.recipient_id}")

    message_id = uuid.uuid4()
    msg_to_client = SendMessageReturn(
        id=message_id,
        sender_id=user_id,
        text=send_msg_input.message,
        time=utc_now(),
        is_viewed=False,
        owning=user_id == send_msg_input.recipient_id,
    )
    new_message = Message(
        id=message_id,
        sender_id=user_id,
        recipient_id=send_msg_input.recipient_id,
        message=send_msg_input.message,
    )
    db_session.add(new_message)
    await asyncio.gather(
        redis.publish(
            channel=str(send_msg_input.recipient_id),
            message=msg_to_client.model_dump_json(),
        ),
        websocket.send_json(msg_to_client.model_dump_json()),
        db_session.commit(),
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
        raise WebsocketError(f"invalid recipient_id: {get_chat_.recipient_id}")

    query = (
        select(Message)
        .where(
            and_(
                Message.recipient_id == get_chat_.recipient_id,
                Message.sender_id == user_id,
            )
        )
        .order_by(Message.created_at)
    )
    result = await db_session.execute(query)
    messages: list[Message] = result.scalars().all()
    get_chat_return = GetChatSchemaReturn(
        user_id=get_chat_.recipient_id,
        messages=[
            MessageInChat(
                id=msg.id,
                text=msg.message,
                time=msg.created_at,
                is_viewed=msg.is_viewed,
                owning=msg.sender_id == user_id,
            )
            for msg in messages
        ],
    )
    await websocket.send_json(get_chat_return.model_dump_json())


async def get_preview(
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
            func.row_number()
            .over(partition_by=Message.sender_id, order_by=desc(Message.created_at))
            .label("rn"),
        )
        .where(Message.recipient_id == user_id)
        .cte("latest_messages")
    )

    query = (
        select(
            User.id,
            User.nickname,
            latest_messages.c.message,
            latest_messages.c.created_at,
            latest_messages.c.is_viewed,
        )
        .join(latest_messages, User.id == latest_messages.c.sender_id)
        .where(latest_messages.c.rn == 1)
        .order_by(desc(latest_messages.c.created_at))
    )

    result = await db_session.execute(query)
    chats_preview = GetPreviewReturn(
        chat_list=(
            ChatPreview(
                user_id=i[0],
                user_nickname=i[1],
                message=i[2],
                last_message_time=i[3],
                is_viewed=i[4],
            )
            for i in result.all()
        )
    )
    await websocket.send_json(chats_preview.model_dump_json())


async def delete_chat(
    websocket: WebSocket,
    db_session: AsyncSession,
    input_: dict,
    user_id: UUID,
):
    try:
        chat_to_delete = DeleteChatScheme.model_validate(input_)
    except KeyError as e:
        raise WebsocketError(e)
    query = delete(Message).where(
        or_(
            and_(
                Message.sender_id == user_id, Message.recipient_id == chat_to_delete.id
            ),
            and_(
                Message.sender_id == chat_to_delete.id, Message.recipient_id == user_id
            ),
        )
    )
    await db_session.execute(query)
    await db_session.commit()


async def read_message(
    websocket: WebSocket,
    input_: dict,
    user_id: UUID,
):
    try:
        readed_message = ReadMessagesForRecipientReturn.model_validate(input_)
    except KeyError as e:
        raise WebsocketError(e)
    redis = get_redis()
    list_message_for_sender = ReadMessagesForSenderReturn(
        recipient_id=user_id, list_message=readed_message.list_message
    )
    if not (
        unsync_read_message := await redis.hget("unsync_read_message", str(user_id))
    ):
        unsync_read_message = ""
    await asyncio.gather(
        redis.hset(
            "unsync_read_message",
            str(user_id),
            unsync_read_message
            + ";".join(str(i) for i in readed_message.list_message)
            + ";",
        ),
        redis.publish(
            channel=f"read_message:{readed_message.sender_id}",
            message=list_message_for_sender.model_dump_json(),
        ),
        websocket.send_json(readed_message.model_dump_json()),
    )


async def chat_input_handler(
    websocket: WebSocket,
    user_id: UUID,
):
    async with async_session_maker() as db_session:
        while True:
            try:
                input_: dict = await websocket.receive_json()
                action_type = input_.get("action_type")
                logger.debug(f"ws: {user_id}: {action_type}")
                match ServerActionType(action_type):
                    case ServerActionType.send_message:
                        await send_message(websocket, db_session, input_, user_id)
                    case ServerActionType.get_chat:
                        await get_chat(websocket, db_session, input_, user_id)
                    case ServerActionType.get_preview:
                        await get_preview(websocket, db_session, user_id)
                    case ServerActionType.read_message:
                        await read_message(websocket, input_, user_id)
                    case ServerActionType.delete_chat:
                        await delete_chat(websocket, db_session, input_, user_id)

            except (WebsocketError, json.decoder.JSONDecodeError, ValueError) as e:
                await websocket.send_json({"error": "invalid json"})
                logger.warning(f"websocket error: {e}")
                continue


async def chat_output_handler(
    websocket: WebSocket,
    user_id: UUID,
):
    async with async_session_maker() as db_session:
        redis = get_redis()
        async with redis.pubsub() as subscribe:
            await subscribe.psubscribe(str(user_id), f"read_message:{user_id}")
            async for msg in subscribe.listen():
                if msg["type"] == "pmessage":
                    data = msg.get("data")
                    await websocket.send_json(data)


@chat.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
):
    user_id: UUID = await get_current_user_id(token=websocket.cookies.get("jwt"))
    await websocket.accept()
    logger.debug(f"Open websocket for {user_id}")

    try:
        await asyncio.gather(
            chat_input_handler(websocket, user_id),
            chat_output_handler(websocket, user_id),
        )
    except WebSocketDisconnect:
        logger.debug(f"Websocket close for {user_id}")
