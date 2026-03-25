from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, BigInteger, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MessageDirection

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.conversation import Conversation
    from app.models.message_analysis import MessageAnalysis


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    direction: Mapped[MessageDirection | None] = mapped_column(
        SQLEnum(MessageDirection, name="message_direction"),
        nullable=True,
    )
    
    # Telegram specific fields for scraping
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True) # Actual Telegram message ID
    telegram_group_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    reply_to_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    
    external_message_id: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ai_draft: Mapped[bool] = mapped_column(default=False, nullable=False)
    human_approved: Mapped[bool] = mapped_column(default=False, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    conversation: Mapped["Conversation | None"] = relationship(back_populates="messages")
    contact: Mapped["Contact | None"] = relationship(back_populates="messages")
    analysis: Mapped["MessageAnalysis | None"] = relationship(back_populates="message", uselist=False, cascade="all, delete-orphan")

