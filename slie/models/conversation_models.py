from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slie.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reply_to_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reply_count: Mapped[int] = mapped_column(default=0)

class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Step 11: CONVERSATION MEMORY ENGINE
    Store previous interactions.
    """
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"))
    messages: Mapped[str] = mapped_column(Text) # JSON or concatenated text
    interaction_history: Mapped[dict] = mapped_column(JSON, default=dict)
    last_interaction: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships would be defined here if we were using consolidated models in one file
    # For now, keeping it simple as per Step 11 requirements.
