from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ClientActionType(Enum):
    status_init = 'status_init'
    get_chat = 'get_chat'
    send_message = 'send_message'


class MessageInRedis(BaseModel):
    message_id: UUID
    sender_id: UUID
    message: str
    message_time: datetime


class MessageToClient(BaseModel):
    sender_id: UUID
    message: str
    message_time: datetime


class RowChat(BaseModel):
    email: str
    nickname: str
    last_message: str
    time_last_message: datetime
    is_read: bool