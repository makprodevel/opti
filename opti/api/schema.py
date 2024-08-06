from uuid import UUID
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: UUID
    email: str
    nickname: str


class ChangeNickname(BaseModel):
    new_nickname: str


class UserInfo(BaseModel):
    id: UUID
    nickname: str


class SearchResult(BaseModel):
    users: list[UserInfo]
