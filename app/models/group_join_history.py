from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class GroupJoinHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_join_history"

    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("telegram_accounts.id", ondelete="CASCADE"), index=True)
    join_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="success") # success, failed

    group = relationship("Group")
    account = relationship("TelegramAccount")
