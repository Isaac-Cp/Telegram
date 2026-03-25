from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.group import Group

class OpportunityCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "problem_clusters"

    problem_type: Mapped[str] = mapped_column(String(255))
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id"))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    group: Mapped["Group"] = relationship()
