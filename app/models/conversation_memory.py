from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class UnifiedConversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "unified_conversations"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"))
    message_text: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(50)) # group_message, public_reply, dm_message, user_reply
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="unified_conversations")

class ConversationSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_summary"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    summary_text: Mapped[str | None] = mapped_column(Text) # Summarized history
    problem_type: Mapped[str | None] = mapped_column(String(100))
    interest_level: Mapped[str | None] = mapped_column(String(50))
    last_problem_detected: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_contacted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conversation_stage: Mapped[str] = mapped_column(String(50), default="new") # new, engaged, follow_up, converted
    message_count_at_last_summary: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="memory_summary")

class LeadValueScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_value_scores"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    ltv_score: Mapped[float] = mapped_column(default=0.0)
    ltv_tier: Mapped[str] = mapped_column(String(50), default="STANDARD BUYER") # RESELLER POTENTIAL, HIGH VALUE BUYER, STANDARD BUYER
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="ltv_score_record")

    @property
    def ltv_level(self) -> str:
        return self.ltv_tier

    @ltv_level.setter
    def ltv_level(self, value: str) -> None:
        self.ltv_tier = value
