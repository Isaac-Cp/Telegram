from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ConversionStage

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.user import User
    from app.models.lead_conversation import LeadConversation
    from app.models.lead_opportunity import LeadOpportunity


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    message_text: Mapped[str] = mapped_column(Text)
    intent_type: Mapped[str | None] = mapped_column(String(50)) # Module 4 Step 5: complaint, help_request
    intent_score: Mapped[float] = mapped_column(default=0.0)
    urgency_score: Mapped[float] = mapped_column(default=0.0)
    opportunity_score: Mapped[float] = mapped_column(default=0.0)
    priority_level: Mapped[str] = mapped_column(String(20), default="LOW") # HIGH, MEDIUM, LOW
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Existing fields (to keep support for old code if needed)
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    lead_strength: Mapped[str | None] = mapped_column(String(50)) # e.g., "ignore", "potential lead", "strong lead"
    first_contact: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_contact: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    public_reply_sent: Mapped[bool] = mapped_column(default=False)
    dm_sent: Mapped[bool] = mapped_column(default=False)
    lead_temperature: Mapped[str | None] = mapped_column(String(20)) # COLD, WARM, HOT
    persona_id: Mapped[str | None] = mapped_column(String(50)) # Aiden, Luca, Maya
    conversion_stage: Mapped[ConversionStage] = mapped_column(
        SQLEnum(ConversionStage, name="conversion_stage"),
        default=ConversionStage.NEW,
        nullable=False,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="leads")
    group: Mapped["Group | None"] = relationship(back_populates="leads")
    conversations: Mapped[list["LeadConversation"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    opportunity: Mapped["LeadOpportunity | None"] = relationship(back_populates="lead", cascade="all, delete-orphan")

