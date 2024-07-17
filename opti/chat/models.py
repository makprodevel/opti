from uuid import UUID
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from opti.auth.models import uuidpk, created_at_c, User
from opti.core.database import DBase


class Message(DBase):
    __tablename__ = "message"

    id: Mapped[uuidpk]
    sender_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    message: Mapped[str] = mapped_column()
    created_at: Mapped[created_at_c]
    is_viewed: Mapped[bool] = mapped_column(server_default=text("false"))
    # sender: Mapped["User"] = relationship(foreign_keys=[sender_id], back_populates='messages_sent')
    # recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id], back_populates='messages_received')


