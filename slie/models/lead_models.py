from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slie.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Activity Metrics
    groups_seen: Mapped[int] = mapped_column(default=0)
    messages_today: Mapped[int] = mapped_column(default=0)
    message_frequency: Mapped[int] = mapped_column(default=0) # Total messages
    complaints_count: Mapped[int] = mapped_column(default=0)
    technical_questions_count: Mapped[int] = mapped_column(default=0)
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_power_user: Mapped[bool] = mapped_column(default=False)

    leads: Mapped[List["Lead"]] = relationship(back_populates="user")
    ltv_scores: Mapped["LeadLTVScore | None"] = relationship(back_populates="user")

class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    message_text: Mapped[str] = mapped_column(Text)
    intent_score: Mapped[float] = mapped_column(default=0.0)
    urgency_score: Mapped[float] = mapped_column(default=0.0)
    opportunity_score: Mapped[float] = mapped_column(default=0.0)
    priority_level: Mapped[str] = mapped_column(String(20), default="LOW") # HIGH, MEDIUM, LOW
    
    user: Mapped["User"] = relationship(back_populates="leads")
    opportunity_scores: Mapped["LeadOpportunityScore | None"] = relationship(back_populates="lead")

class LeadOpportunityScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_opportunity_scores"

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), unique=True, index=True)
    intent_score: Mapped[float] = mapped_column(default=0.0)
    urgency_score: Mapped[float] = mapped_column(default=0.0)
    activity_score: Mapped[float] = mapped_column(default=0.0)
    opportunity_score: Mapped[float] = mapped_column(default=0.0)
    priority_level: Mapped[str] = mapped_column(String(20), default="LOW")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="opportunity_scores")

class LeadLTVScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_ltv_scores"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    ltv_score: Mapped[float] = mapped_column(default=0.0)
    ltv_tier: Mapped[str] = mapped_column(String(50), default="STANDARD BUYER") # RESELLER_POTENTIAL, HIGH_VALUE_BUYER, STANDARD_BUYER
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="ltv_scores")
