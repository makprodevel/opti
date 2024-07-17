from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ActionBase(BaseModel):
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, 'action_type'):
            raise TypeError(f"Class {cls.__name__} must define 'action_type' attribute.")
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
    action_type: str = 'chat'
    messages: list[MessageInChat]


class SendMessageSchema(BaseModel):
    recipient_id: UUID
    message: str


class MessageToClient(MessageInChat, ActionBase):
    action_type: str = 'sended_message'
    sender_id: UUID


class RowChat(BaseModel):
    id: UUID
    nickname: str
    last_message: str
    time_last_message: datetime
    is_read: bool


class ReadedMessagesForRecipient(ActionBase):
    action_type: str = 'readed_message'
    sender_id: UUID
    list_message: list[UUID]


class ReadedMessagesForSender(ActionBase):
    action_type: str = "readed_message"
    recipient_id: UUID
    list_message: list[UUID]


class ChatPreview(BaseModel):
    user_id: UUID
    user_nickname: str
    message: str
    last_message_time: datetime
    is_viewed: bool


class StatusInit(ActionBase):
    action_type: str = 'status_init'
    chat_list: list[ChatPreview]


