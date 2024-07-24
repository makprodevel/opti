from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ActionBase(BaseModel):
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "action_type"):
            raise TypeError(
                f"Class {cls.__name__} must define 'action_type' attribute."
            )
        if not isinstance(cls.action_type, (ClientActionType, ServerActionType)):
            raise TypeError(
                f"The 'action_type' attribute in class {cls.__name__} must be of type ClientActionType or ServerActionType."
            )

        super().__init_subclass__(**kwargs)


class ServerError(BaseModel):
    error: str


class ClientActionType(Enum):
    get_preview = "get_preview"
    get_chat = "get_chat"
    receive_message = "receive_message"
    read_message = "read_message"
    delete_chat = "delete_chat"


class ServerActionType(Enum):
    get_preview = "get_preview"
    get_chat = "get_chat"
    send_message = "send_message"
    read_message = "read_message"
    delete_chat = "delete_chat"


class GetChatSchema(BaseModel):
    recipient_id: UUID


class MessageInChat(BaseModel):
    id: UUID
    text: str
    time: datetime
    is_viewed: bool
    owning: bool


class GetChatSchemaReturn(ActionBase):
    action_type: ClientActionType = ClientActionType.get_chat
    user_id: UUID
    messages: list[MessageInChat]


class SendMessageSchema(BaseModel):
    recipient_id: UUID
    message: str


class SendMessageReturn(MessageInChat, ActionBase):
    action_type: ClientActionType = ClientActionType.receive_message
    sender_id: UUID


class RowChat(BaseModel):
    id: UUID
    nickname: str
    last_message: str
    time_last_message: datetime
    is_read: bool


class ReadMessagesForRecipientReturn(ActionBase):
    action_type: ClientActionType = ClientActionType.read_message
    sender_id: UUID
    list_message: list[UUID]


class ReadMessagesForSenderReturn(ActionBase):
    action_type: ClientActionType = ClientActionType.read_message
    recipient_id: UUID
    list_message: list[UUID]


class ChatPreview(BaseModel):
    user_id: UUID
    user_nickname: str
    message: str
    last_message_time: datetime
    is_viewed: bool


class GetPreviewReturn(ActionBase):
    action_type: ClientActionType = ClientActionType.get_preview
    chat_list: list[ChatPreview]


class DeleteChatScheme(ActionBase):
    action_type: ClientActionType = ClientActionType.delete_chat
    id: UUID
