from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ActionBase(BaseModel):
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, 'type_'):
            raise TypeError(f"Class {cls.__name__} must define 'type_' attribute.")
        super().__init_subclass__(**kwargs)


class ServerError(BaseModel):
    error: str


class ClientActionType(Enum):
    status_init = 'status_init'
    get_chat = 'get_chat'
    send_message = 'send_message'
    readed_message = 'readed_message'


class GetChatSchema(BaseModel):
    recipient_id: UUID


class MessageInChat(BaseModel):
    message_id: UUID
    message: str
    message_time: datetime


class GetChatSchemaReturn(ActionBase):
    type_: str = 'chat'
    messages: list[MessageInChat]


class SendMessageSchema(BaseModel):
    recipient_id: UUID
    message: str


class MessageToClient(MessageInChat, ActionBase):
    type_: str = 'sended_message'
    sender_id: UUID


class RowChat(BaseModel):
    id: UUID
    nickname: str
    last_message: str
    time_last_message: datetime
    is_read: bool


class ReadedMessage(BaseModel):
    id: UUID


class ChatPreview(BaseModel):
    user_id: UUID
    user_nickname: str
    message: str
    last_message_time: datetime
    is_viewed: bool


class StatusInit(ActionBase):
    type_: str = 'status_init'
    chat_list: list[ChatPreview]
