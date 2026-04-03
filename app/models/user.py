from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import BigInteger, DateTime, String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.conversation_memory import UnifiedConversation, LeadValueScore, ConversationSummary
    from app.models.cross_group_identity import CrossGroupIdentity

class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    influence_level: Mapped[str | None] = mapped_column(String(50)) # reseller, admin, power_user, etc
    message_frequency: Mapped[int] = mapped_column(Integer, default=0) # Total messages count
    messages_today: Mapped[int] = mapped_column(Integer, default=0) # Module 4 Step 6
    groups_seen: Mapped[int] = mapped_column(Integer, default=0) # Module 4 Step 6
    complaints_count: Mapped[int] = mapped_column(Integer, default=0) # Module 6 Step 4
    technical_questions_count: Mapped[int] = mapped_column(Integer, default=0) # Module 6 Step 4
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_power_user: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    leads: Mapped[list["Lead"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    cross_group_identities: Mapped[list["CrossGroupIdentity"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    unified_conversations: Mapped[list["UnifiedConversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ltv_score_record: Mapped["LeadValueScore | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    memory_summary: Mapped["ConversationSummary | None"] = relationship(back_populates="user", cascade="all, delete-orphan")

