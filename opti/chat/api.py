import uuid
from uuid import UUID
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, delete, or_, case

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
        user_id: UUID,
        data: SendMessageSchema
):
    redis = get_redis()
    if not await valid_user_from_db(data.recipient_id):
        raise WebsocketError(f"invalid recipient_id: {data.recipient_id}")

    message_id = uuid.uuid4()
    msg_to_this_user = SendMessageReturn(
        id=message_id,
        other_id=data.recipient_id,
        text=data.message,
        time=utc_now(),
        is_viewed=False,
        owning=True,
    )
    msg_to_other_user = SendMessageReturn(
        id=message_id,
        other_id=user_id,
        text=data.message,
        time=utc_now(),
        is_viewed=False,
        owning=False,
    )
    new_message = Message(
        id=message_id,
        sender_id=user_id,
        recipient_id=data.recipient_id,
        message=data.message,
    )
    db_session.add(new_message)
    await asyncio.gather(
        redis.publish(
            channel=str(data.recipient_id),
            message=msg_to_other_user.model_dump_json(),
        ),
        websocket.send_json(msg_to_this_user.model_dump_json()),
        db_session.commit(),
    )


async def get_chat(
        websocket: WebSocket,
        db_session: AsyncSession,
        user_id: UUID,
        data: GetChatSchema
):
    if not await valid_user_from_db(data.recipient_id):
        raise WebsocketError(f"invalid recipient_id: {data.recipient_id}")

    query = (
        select(Message)
        .where(
            or_(
                and_(
                    Message.recipient_id == data.recipient_id,
                    Message.sender_id == user_id,
                ),
                and_(
                    Message.sender_id == data.recipient_id,
                    Message.recipient_id == user_id,
                )
            )
        )
        .order_by(Message.created_at)
    )
    result = await db_session.execute(query)
    messages: list[Message] = result.scalars().all()
    get_chat_return = GetChatSchemaReturn(
        user_id=data.recipient_id,
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
            .over(
                partition_by=(func.least(Message.sender_id, Message.recipient_id),
                              func.greatest(Message.sender_id, Message.recipient_id)),
                order_by=desc(Message.created_at)
            )
            .label("rn"),
            case(
                (Message.sender_id == user_id, Message.recipient_id),
                (Message.recipient_id == user_id, Message.sender_id)
            ).label("other_user_id")
        )
        .where(or_(Message.recipient_id == user_id, Message.sender_id == user_id))
        .cte("latest_messages")
    )

    unread_message_counts = (
        select(
            func.least(Message.sender_id, Message.recipient_id).label("user1_id"),
            func.greatest(Message.sender_id, Message.recipient_id).label("user2_id"),
            func.count().label("message_count")
        )
        .where(Message.is_viewed == False)
        .group_by(
            func.least(Message.sender_id, Message.recipient_id),
            func.greatest(Message.sender_id, Message.recipient_id)
        )
        .cte("message_counts")
    )

    query = (
        select(
            User.id,
            User.nickname,
            latest_messages.c.message,
            latest_messages.c.created_at,
            latest_messages.c.is_viewed,
            func.coalesce(unread_message_counts.c.message_count, 0).label("unread_count")
        )
        .join(User, User.id == latest_messages.c.other_user_id)
        .join(
            unread_message_counts,
            and_(
                unread_message_counts.c.user1_id == func.least(user_id, latest_messages.c.other_user_id),
                unread_message_counts.c.user2_id == func.greatest(user_id, latest_messages.c.other_user_id)
            )
        )
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
                count=i[5]
            )
            for i in result.all()
        )
    )
    await websocket.send_json(chats_preview.model_dump_json())


async def delete_chat(
        websocket: WebSocket,
        db_session: AsyncSession,
        user_id: UUID,
        data: DeleteChatScheme
):
    query = delete(Message).where(
        or_(
            and_(
                Message.sender_id == user_id, Message.recipient_id == data.id
            ),
            and_(
                Message.sender_id == data.id, Message.recipient_id == user_id
            ),
        )
    )
    await db_session.execute(query)
    await db_session.commit()


async def read_message(
        websocket: WebSocket,
        user_id: UUID,
        data: ReadMessagesForRecipientReturn
):
    redis = get_redis()
    list_message_for_sender = ReadMessagesForSenderReturn(
        recipient_id=user_id, list_message=data.list_message
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
            + ";".join(str(i) for i in data.list_message)
            + ";",
        ),
        redis.publish(
            channel=f"read_message:{data.sender_id}",
            message=list_message_for_sender.model_dump_json(),
        ),
        websocket.send_json(data.model_dump_json()),
    )


async def chat_input_handler(
        websocket: WebSocket,
        user_id: UUID,
):
    async with async_session_maker() as db_session:
        while True:
            try:
                ws_data: dict = await websocket.receive_json()
                try:
                    action_type = ServerActionType(ws_data.get("action_type"))
                except ValueError:
                    raise WebsocketError('invalid action')
                logger.debug(f"ws: {user_id}: {action_type.value}")

                action_list = {
                    ServerActionType.send_message: (send_message, SendMessageSchema, (db_session, user_id)),
                    ServerActionType.get_chat: (get_chat, GetChatSchema, (db_session, user_id)),
                    ServerActionType.get_preview: (get_preview, None, (db_session, user_id)),
                    ServerActionType.read_message: (read_message, ReadMessagesForRecipientReturn, (user_id,)),
                    ServerActionType.delete_chat: (delete_chat, DeleteChatScheme, (db_session, user_id)),
                }

                func, schema, params = action_list[action_type]

                if schema is not None:
                    try:
                        data = schema.model_validate(ws_data)
                        params = params + (data,)
                    except (KeyError, ValueError, ValidationError) as e:
                        raise WebsocketError(e)
                await func(websocket, *params)


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
