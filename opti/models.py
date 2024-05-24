from sqlalchemy import Column, String, Boolean, TIMESTAMP, func
from opti.database import DBase


class User(DBase):
    __tablename__ = "user"

    email = Column(String, nullable=False, primary_key=True, unique=True)
    nickname = Column(String, nullable=False)
    is_superuser = Column(Boolean, nullable=False, default=False)
    registered_at = Column(TIMESTAMP, default=func.now())
    online_at = Column(TIMESTAMP, default=func.now())
    is_blocked = Column(Boolean, nullable=False, default=False)
