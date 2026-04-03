from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class Group(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "groups"

    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    invite_link: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    members_count: Mapped[int] = mapped_column(Integer, default=0)
    messages_last_24h: Mapped[int] = mapped_column(Integer, default=0)
    unique_users_last_24h: Mapped[int] = mapped_column(Integer, default=0)
    last_message_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(32), default="en")
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    authority_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="new") # new, analyzed, approved, joined, rejected
    discovery_source: Mapped[str | None] = mapped_column(String(50)) # search, link, reddit, forum
    seller_density: Mapped[float] = mapped_column(default=0.0)
    discussion_signal: Mapped[int] = mapped_column(Integer, default=0) # Module 2: Buyer discussion count
    saturation_status: Mapped[str | None] = mapped_column(String(32)) # opportunity, competitive, saturated
    joined: Mapped[bool] = mapped_column(Boolean, default=False)
    eligible_for_join: Mapped[bool] = mapped_column(Boolean, default=False)
    date_discovered: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_scanned: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    leads: Mapped[list["Lead"]] = relationship(back_populates="group")
