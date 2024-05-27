from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ServerError(BaseModel):
    error: str


class ClientActionType(Enum):
    status_init = 'status_init'
    get_chat = 'get_chat'
    send_message = 'send_message'


class GetChatSchema(BaseModel):
    recipient_id: UUID


class MessageInChat(BaseModel):
    message_id: UUID
    message: str
    message_time: datetime


class GetChatReturnSchema(BaseModel):
    messages: list[MessageInChat]


class SendMessageSchema(BaseModel):
    recipient_id: UUID
    message: str


class MessageToClient(MessageInChat):
    sender_id: UUID


class RowChat(BaseModel):
    id: UUID
    nickname: str
    last_message: str
    time_last_message: datetime
    is_read: bool
