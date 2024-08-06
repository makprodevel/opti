from uuid import UUID
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from opti.chat.schema import (
    SendMessageSchema,
    GetChatSchema,
    ReadMessagesForRecipientReturn,
    ServerActionType,
    DeleteChatScheme,
)
from opti.chat.service import send_message, get_chat, get_preview, delete_chat, read_message, user_status_online, \
    user_status_offline
from opti.chat.utils import WebsocketError
from opti.core.database import async_session_maker
from opti.core.redis import get_redis
from opti.core.config import logger
from opti.auth.service import get_current_user_id


chat = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


async def chat_input_handler(
    websocket: WebSocket,
    user_id: UUID,
):
    async with async_session_maker() as db_session:
        await get_preview(websocket, db_session, user_id)
        while True:
            try:
                ws_data: dict = await websocket.receive_json()
                try:
                    action_type = ServerActionType(ws_data.get("action_type"))
                except ValueError:
                    raise WebsocketError('invalid action')
                logger.debug(f"ws: {user_id}: {action_type.value}")

                action_list = {
                    ServerActionType.send_message: (send_message, SendMessageSchema),
                    ServerActionType.get_chat: (get_chat, GetChatSchema),
                    ServerActionType.read_message: (read_message, ReadMessagesForRecipientReturn),
                    ServerActionType.delete_chat: (delete_chat, DeleteChatScheme),
                }

                func, schema = action_list[action_type]

                try:
                    data = schema.model_validate(ws_data)
                except (KeyError, ValueError, ValidationError) as e:
                    raise WebsocketError(e)
                await func(websocket, db_session, user_id, data)


            except (WebsocketError, json.decoder.JSONDecodeError, ValueError) as e:
                await websocket.send_json({"error": "invalid json"})
                logger.warning(f"websocket error: {e}")
                continue


async def chat_output_handler(
    websocket: WebSocket,
    user_id: UUID,
):
    redis = get_redis()
    async with redis.pubsub() as subscribe:
        await subscribe.psubscribe(str(user_id))
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
    await user_status_online(user_id)
    logger.debug(f"Open websocket for {user_id}")

    try:
        await asyncio.gather(
            chat_input_handler(websocket, user_id),
            chat_output_handler(websocket, user_id),
        )
    except WebSocketDisconnect:
        await user_status_offline(user_id)
        logger.debug(f"Websocket close for {user_id}")
