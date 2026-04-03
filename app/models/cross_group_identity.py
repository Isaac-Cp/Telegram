from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class CrossGroupIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Tracks user appearances across multiple Telegram groups.
    Part of Cross-Group Identity Tracking (Elite Module 4).
    """
    __tablename__ = "cross_group_identities"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    first_seen_in_group: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_in_group: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="cross_group_identities")
    group = relationship("Group")
