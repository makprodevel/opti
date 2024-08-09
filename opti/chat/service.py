import asyncio
import uuid
from typing import Sequence
from uuid import UUID
from sqlalchemy import select, or_, and_, func, desc, case, delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket

from opti.auth.models import User
from opti.auth.service import valid_user_from_db
from opti.chat.models import Message
from opti.chat.schema import SendMessageSchema, ClientReceiveMessagesSchema, GetChatSchema, MessageInChat, \
    GetPreviewReturn, ChatPreview, DeleteChatScheme, UserInfo, ReadMessagesSchema, ClientReadMessagesSchema, \
    ClientDeleteChatScheme
from opti.chat.utils import WebsocketError
from opti.core.redis import get_redis
from opti.core.utils import utc_now


async def get_preview(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_id: UUID,
):
    unread_messages_count = (
        select(
            Message.sender_id,
            Message.recipient_id,
            func.count().label("unread_count")
        )
        .where(and_(
            Message.is_viewed.is_(False),
            Message.sender_id != user_id
        ))
        .group_by(Message.recipient_id, Message.sender_id)
        .cte("unread_messages_count")
    )

    latest_messages = (
        select(
            Message,
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

    query = (
        select(
            User.id,
            User.nickname,
            latest_messages.c.id,
            latest_messages.c.sender_id,
            latest_messages.c.recipient_id,
            latest_messages.c.message,
            latest_messages.c.created_at,
            latest_messages.c.is_viewed,
            func.coalesce(unread_messages_count.c.unread_count, 0).label("unread_count")
        )
        .outerjoin(latest_messages, User.id == latest_messages.c.other_user_id)
        .outerjoin(unread_messages_count, and_(
            user_id == unread_messages_count.c.recipient_id,
            User.id == unread_messages_count.c.sender_id,
        ))
        .where(latest_messages.c.rn == 1)
        .order_by(desc(latest_messages.c.created_at))
    )

    result = await db_session.execute(query)
    chats_preview = GetPreviewReturn(
        chat_list=(
            ChatPreview(
                user=UserInfo(
                    id=i[0],
                    nickname=i[1],
                ),
                last_message=MessageInChat(
                    id=i[2],
                    sender_id=i[3],
                    recipient_id=i[4],
                    text=i[5],
                    time=i[6],
                    is_viewed=i[7]
                ),
                count_unread_message=i[8]
            )
            for i in result.all()
        )
    )
    await websocket.send_json(chats_preview.model_dump_json())


async def get_chat(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_id: UUID,
    data: GetChatSchema
):
    if not await valid_user_from_db(data.user_id):
        raise WebsocketError(f"invalid recipient_id: {data.user_id}")

    query = (
        select(Message)
        .where(
            or_(
                and_(
                    Message.recipient_id == data.user_id,
                    Message.sender_id == user_id,
                ),
                and_(
                    Message.sender_id == data.user_id,
                    Message.recipient_id == user_id,
                )
            )
        )
        .order_by(Message.created_at)
    )
    result = await db_session.execute(query)
    messages: Sequence[Message] = result.scalars().all()
    get_chat_return = ClientReceiveMessagesSchema(
        user_id=data.user_id,
        messages=[
            MessageInChat(
                id=msg.id,
                sender_id=msg.sender_id,
                recipient_id=msg.recipient_id,
                text=msg.message,
                time=msg.created_at,
                is_viewed=msg.is_viewed,
            )
            for msg in messages
        ],
    )
    await websocket.send_json(get_chat_return.model_dump_json())


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
    send_message_return = ClientReceiveMessagesSchema(
        messages=[MessageInChat(
            id=message_id,
            sender_id=user_id,
            recipient_id=data.recipient_id,
            text=data.message,
            time=utc_now(),
            is_viewed=False
        )]
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
            message=send_message_return.model_dump_json(),
        ),
        websocket.send_json(send_message_return.model_dump_json()),
        db_session.commit()
    )


async def read_message(
    websocket: WebSocket,
    _: AsyncSession,
    user_id: UUID,
    data: ReadMessagesSchema
):
    redis = get_redis()
    data_to_client = ClientReadMessagesSchema(list_messages_id=data.list_messages_id)
    if not (unsync_read_message := await redis.hget("unsync_read_message", str(user_id))):
        unsync_read_message = ""
    unsync_read_message += ";".join(str(i) for i in data.list_messages_id) + ";"
    await asyncio.gather(
        redis.hset(
            "unsync_read_message",
            str(user_id),
            unsync_read_message
        ),
        redis.publish(
            channel=str(data.other_user_id),
            message=data_to_client.model_dump_json(),
        ),
        websocket.send_json(data_to_client.model_dump_json()),
    )


async def delete_chat(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_id: UUID,
    data: DeleteChatScheme
):
    redis = get_redis()
    query = delete(Message).where(
        or_(
            and_(
                Message.sender_id == user_id, Message.recipient_id == data.user_id
            ),
            and_(
                Message.sender_id == data.user_id, Message.recipient_id == user_id
            ),
        )
    )
    await db_session.execute(query)
    await db_session.commit()
    await asyncio.gather(
        redis.publish(
            channel=str(data.user_id),
            message=ClientDeleteChatScheme(other_user_id=user_id).model_dump_json(),
        ),
        websocket.send_json(ClientDeleteChatScheme(other_user_id=data.user_id).model_dump_json()),
    )


async def user_status_online(user_id: UUID):
    pass


async def user_status_offline(user_id: UUID):
    pass
