from datetime import datetime
from sqlalchemy import String, Float, DateTime, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class CompetitorInsight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    MODULE 2 - COMPETITOR WEAKNESS SCANNER
    Identify weaknesses in competing IPTV services based on user discussions.
    """
    __tablename__ = "competitor_insights"

    competitor_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    complaint_count: Mapped[int] = mapped_column(Integer, default=0)
    complaint_types: Mapped[dict] = mapped_column(JSON, default=dict) # buffering, server_down, etc.
    unique_users_reporting: Mapped[int] = mapped_column(Integer, default=0)
    complaint_frequency: Mapped[float] = mapped_column(Float, default=0.0) # complaints per day
    weakness_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
