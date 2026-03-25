from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import FollowUpJobStatus, FollowUpJobType

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.ticket import Ticket


class FollowUpJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "follow_up_jobs"

    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"), index=True)
    job_type: Mapped[FollowUpJobType] = mapped_column(
        SQLEnum(FollowUpJobType, name="follow_up_job_type"),
        nullable=False,
    )
    status: Mapped[FollowUpJobStatus] = mapped_column(
        SQLEnum(FollowUpJobStatus, name="follow_up_job_status"),
        default=FollowUpJobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    contact: Mapped["Contact"] = relationship(back_populates="follow_up_jobs")
    ticket: Mapped["Ticket | None"] = relationship(back_populates="follow_up_jobs")

