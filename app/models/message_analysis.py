from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.message import Message


class MessageAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_analysis"
    __table_args__ = (
        Index("ix_dashboard_message_analysis_problem_type", "problem_type"),
    )

    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), unique=True, index=True)
    classification: Mapped[int] = mapped_column(Integer, default=0) # 0, 1, 2
    problem_type: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)

    message: Mapped["Message"] = relationship(back_populates="analysis")
