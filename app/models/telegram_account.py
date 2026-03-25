from sqlalchemy import String, Integer, BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class TelegramAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_accounts"

    phone_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    session_file: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active") # active, limited, banned
    groups_joined: Mapped[int] = mapped_column(Integer, default=0)
    daily_dm_count: Mapped[int] = mapped_column(Integer, default=0)
    daily_reply_count: Mapped[int] = mapped_column(Integer, default=0)
    api_id: Mapped[int | None] = mapped_column(Integer)
    api_hash: Mapped[str | None] = mapped_column(String(255))
    
    # Proxy fields (Module 2 Safety)
    proxy_host: Mapped[str | None] = mapped_column(String(255))
    proxy_port: Mapped[int | None] = mapped_column(Integer)
    proxy_type: Mapped[str | None] = mapped_column(String(20)) # socks5, http
    proxy_user: Mapped[str | None] = mapped_column(String(255))
    proxy_pass: Mapped[str | None] = mapped_column(String(255))

