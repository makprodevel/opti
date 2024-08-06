from typing import Annotated
from sqlalchemy import text, Index
from opti.core.database import DBase
from sqlalchemy.orm import mapped_column, Mapped
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

    __table_args__ = (
        Index(
            'idx_users_nickname_trgm',
            text("nickname gin_trgm_ops"),
            postgresql_using='gin'
        ),
    )