from datetime import datetime
from sqlalchemy import ForeignKey, String, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ConversionPrediction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    MODULE 3 - CONVERSION PROBABILITY ENGINE
    Predict the probability that a detected lead will convert.
    """
    __tablename__ = "conversion_predictions"

    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), unique=True, index=True)
    conversion_probability: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_tier: Mapped[str] = mapped_column(String(50), default="low_conversion_probability") # high, medium, low
    
    # Feature scores (normalized 0-1)
    opportunity_score_norm: Mapped[float] = mapped_column(Float, default=0.0)
    ltv_score_norm: Mapped[float] = mapped_column(Float, default=0.0)
    influence_score_norm: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_score_norm: Mapped[float] = mapped_column(Float, default=0.0)

    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    lead = relationship("Lead")
