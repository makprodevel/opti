from sqlalchemy import Column, String, Boolean, TIMESTAMP, UUID, func, ForeignKey, Text
from opti.core.database import DBase
from sqlalchemy.orm import relationship
import uuid


class User(DBase):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    nickname = Column(String, nullable=False)
    is_superuser = Column(Boolean, nullable=False, default=False)
    registered_at = Column(TIMESTAMP, default=func.now())
    #online_at = Column(TIMESTAMP, default=func.now())
    is_blocked = Column(Boolean, nullable=False, default=False)


class Message(DBase):
    __tablename__ = "message"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    sender = relationship('User', back_populates='message')
    recipient_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    recipient = relationship('User', back_populates='message')
    message = Column(Text, nullable=False)


User.messages_sent = relationship('Message', back_populates='sender', foreign_keys=[Message.sender_id])
User.messages_received = relationship('Message', back_populates='recipient', foreign_keys=[Message.recipient_id])

Message.sender = relationship('User', foreign_keys=[Message.sender_id], back_populates='messages_sent')
Message.recipient = relationship('User', foreign_keys=[Message.recipient_id], back_populates='messages_received')
