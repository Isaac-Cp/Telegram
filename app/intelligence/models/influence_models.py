from datetime import datetime
from sqlalchemy import ForeignKey, String, Float, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class InfluenceProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    MODULE 1 - COMMUNITY INFLUENCE GRAPH ENGINE
    Identify influential users inside Telegram communities.
    """
    __tablename__ = "influence_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    influence_score: Mapped[float] = mapped_column(Float, default=0.0)
    influence_level: Mapped[str] = mapped_column(String(50), default="regular_member") # community_leader, power_user, regular_member
    
    # Metrics for score calculation
    messages_sent_24h: Mapped[int] = mapped_column(Integer, default=0)
    replies_received: Mapped[int] = mapped_column(Integer, default=0)
    mentions_received: Mapped[int] = mapped_column(Integer, default=0)
    threads_started: Mapped[int] = mapped_column(Integer, default=0)
    
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User")
    group = relationship("Group")
