from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TicketCategory, TicketPriority, TicketStatus

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.conversation import Conversation
    from app.models.follow_up_job import FollowUpJob


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[TicketCategory] = mapped_column(SQLEnum(TicketCategory, name="ticket_category"), nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(
        SQLEnum(TicketPriority, name="ticket_priority"),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )
    status: Mapped[TicketStatus] = mapped_column(
        SQLEnum(TicketStatus, name="ticket_status"),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contact: Mapped["Contact"] = relationship(back_populates="tickets")
    conversation: Mapped["Conversation | None"] = relationship(back_populates="tickets")
    follow_up_jobs: Mapped[list["FollowUpJob"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")

