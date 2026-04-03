from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ContactStatus

if TYPE_CHECKING:
    from app.models.activity_event import ActivityEvent
    from app.models.consent import Consent
    from app.models.conversation import Conversation
    from app.models.follow_up_job import FollowUpJob
    from app.models.lead_profile import LeadProfile
    from app.models.message import Message
    from app.models.ticket import Ticket


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"

    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(100), default="telegram")
    status: Mapped[ContactStatus] = mapped_column(
        SQLEnum(ContactStatus, name="contact_status"),
        default=ContactStatus.NEW,
        nullable=False,
    )
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    consents: Mapped[list["Consent"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    follow_up_jobs: Mapped[list["FollowUpJob"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    activity_events: Mapped[list["ActivityEvent"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    lead_profile: Mapped["LeadProfile | None"] = relationship(back_populates="contact", uselist=False, cascade="all, delete-orphan")

