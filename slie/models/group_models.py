from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from slie.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin

class Group(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "groups"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    member_count: Mapped[int] = mapped_column(default=0)
    is_public: Mapped[bool] = mapped_column(default=True)
    can_post: Mapped[bool] = mapped_column(default=True)
    joined: Mapped[bool] = mapped_column(default=False)
    
    # Discovery Metrics
    authority_score: Mapped[float] = mapped_column(default=0.0)
    seller_density: Mapped[float] = mapped_column(default=0.0)
    saturation_status: Mapped[str | None] = mapped_column(String(50)) # DISCUSSION_GROUP, MIXED_GROUP, SELLER_HUB
    eligible_for_join: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="DISCOVERED") # DISCOVERED, APPROVED, REJECTED, JOINED

    market_analysis: Mapped["GroupMarketAnalysis | None"] = relationship(back_populates="group")

class GroupJoinHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_join_history"

    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    account_phone: Mapped[str] = mapped_column(String(50))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20)) # success, failed

class GroupMarketAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_market_analysis"

    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), unique=True, index=True)
    seller_ratio: Mapped[float] = mapped_column(default=0.0)
    market_type: Mapped[str] = mapped_column(String(50)) # SELLER_HUB, MIXED_GROUP, DISCUSSION_GROUP
    promotional_msg_count: Mapped[int] = mapped_column(default=0)
    total_msg_analyzed: Mapped[int] = mapped_column(default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    group: Mapped["Group"] = relationship(back_populates="market_analysis")
