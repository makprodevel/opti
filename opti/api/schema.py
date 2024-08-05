from pydantic import BaseModel


class CurrentUser(BaseModel):
    email: str
    nickname: str


class ChangeNickname(BaseModel):
    new_nickname: str
