from typing import Annotated
from sqlalchemy import ForeignKey, text
from opti.core.database import DBase
from sqlalchemy.orm import relationship, mapped_column, Mapped
from uuid import UUID
from datetime import datetime


uuidpk = Annotated[UUID, mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))]
created_at_c = Annotated[datetime, mapped_column(server_default=text("TIMEZONE('utc', now())"))]


class User(DBase):
    __tablename__ = "users"

    id: Mapped[uuidpk]
    email: Mapped[str] = mapped_column(unique=True)
    nickname: Mapped[str] = mapped_column()
    is_superuser: Mapped[bool] = mapped_column(server_default=text("false"))
    registered_at: Mapped[created_at_c]
    is_blocked: Mapped[bool] = mapped_column(server_default=text("false"))
    messages_sent: Mapped["Message"] = relationship(foreign_keys="[Message.sender_id]", back_populates='sender')
    messages_received: Mapped["Message"] = relationship(foreign_keys="[Message.recipient_id]",  back_populates='recipient')


class Message(DBase):
    __tablename__ = "message"

    id: Mapped[uuidpk]
    sender_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    message: Mapped[str] = mapped_column()
    created_at: Mapped[created_at_c]
    is_viewed: Mapped[bool] = mapped_column(server_default=text("false"))
    sender: Mapped["User"] = relationship(foreign_keys=[sender_id], back_populates='messages_sent')
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id], back_populates='messages_received')
