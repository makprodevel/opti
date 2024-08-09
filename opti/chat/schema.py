from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel


class BaseAction(BaseModel):
    '''mark action data class'''
    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "action_type"):
            raise TypeError(
                f"Class {cls.__name__} must define 'action_type' attribute."
            )
        if not isinstance(cls.action_type, (ClientActionType, ServerActionType)):
            raise TypeError(
                f"The 'action_type' attribute in class {cls.__name__} must be ClientActionType or ServerActionType."
            )

        super().__init_subclass__(**kwargs)


class ClientActionType(Enum):
    '''type request to client'''
    get_preview = "get_preview"
    receive_messages = "receive_messages"
    read_messages = "read_messages"
    delete_chat = "delete_chat"


class ServerActionType(Enum):
    '''type request to server'''
    get_chat = "get_chat"
    send_message = "send_message"
    read_messages = "read_messages"
    delete_chat = "delete_chat"


class MessageInChat(BaseModel):
    id: UUID
    sender_id: UUID
    recipient_id: UUID
    text: str
    time: datetime
    is_viewed: bool


class UserInfo(BaseModel):
    id: UUID
    nickname: str


class ChatPreview(BaseModel):
    user: UserInfo
    last_message: MessageInChat
    count_unread_message: int


class GetPreviewReturn(BaseAction):
    action_type: ClientActionType = ClientActionType.get_preview
    chat_list: list[ChatPreview]


class GetChatSchema(BaseAction):
    action_type: ServerActionType = ServerActionType.get_chat
    user_id: UUID


class ClientReceiveMessagesSchema(BaseAction):
    action_type: ClientActionType = ClientActionType.receive_messages
    messages: list[MessageInChat]


class SendMessageSchema(BaseAction):
    action_type: ServerActionType = ServerActionType.send_message
    recipient_id: UUID
    message: str


class ReadMessagesSchema(BaseAction):
    action_type: ServerActionType = ServerActionType.read_messages
    other_user_id: UUID
    list_messages_id: list[UUID]


class ClientReadMessagesSchema(BaseAction):
    action_type: ClientActionType = ClientActionType.read_messages
    list_messages_id: list[UUID]


class DeleteChatScheme(BaseAction):
    action_type: ServerActionType = ServerActionType.delete_chat
    user_id: UUID


class ClientDeleteChatScheme(BaseAction):
    action_type: ClientActionType = ClientActionType.delete_chat
    other_user_id: UUID
