from sqlalchemy import ForeignKey, Integer, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class LeadOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_opportunities"

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), unique=True, index=True)
    intent_score: Mapped[int] = mapped_column(Integer, default=1)
    influence_score: Mapped[int] = mapped_column(Integer, default=2)
    urgency_score: Mapped[int] = mapped_column(Integer, default=1)
    seller_density: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_level: Mapped[str] = mapped_column(String(20), default="LOW") # HIGH, MEDIUM, LOW
    priority_tier: Mapped[int] = mapped_column(Integer, default=3) # 1, 2, 3

    lead: Mapped["Lead"] = relationship(back_populates="opportunity")
