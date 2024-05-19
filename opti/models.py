import uuid
from sqlalchemy import Column, UUID, String, Boolean, TIMESTAMP
from opti.database import DBase
from .utils import utc_now


class User(DBase):
    __tablename__ = "user"

    email = Column(String, nullable=False, primary_key=True, unique=True)
    nickname = Column(String, nullable=False)
    is_superuser = Column(Boolean, nullable=False)
    registered_at = Column(TIMESTAMP, default=utc_now)
    online_at = Column(TIMESTAMP)
