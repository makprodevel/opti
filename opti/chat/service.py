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
from opti.chat.schema import SendMessageSchema, SendMessageReturn, GetChatSchema, GetChatSchemaReturn, MessageInChat, \
    GetPreviewReturn, ChatPreview, DeleteChatScheme, ReadMessagesForSenderReturn, ReadMessagesForRecipientReturn
from opti.chat.utils import WebsocketError
from opti.core.redis import get_redis
from opti.core.utils import utc_now


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
    messages: Sequence[Message] = result.scalars().all()
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
    db_session: AsyncSession,
    user_id: UUID,
    data: ReadMessagesForRecipientReturn
):
    redis = get_redis()
    list_message_for_sender = ReadMessagesForSenderReturn(
        recipient_id=user_id,
        list_message=data.list_message
    )
    if not (unsync_read_message := await redis.hget("unsync_read_message", str(user_id))):
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
            channel=str(data.sender_id),
            message=list_message_for_sender.model_dump_json(),
        ),
        websocket.send_json(data.model_dump_json()),
    )


async def user_status_online(user_id: UUID):
    pass


async def user_status_offline(user_id: UUID):
    pass
