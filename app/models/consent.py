from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ConsentChannel, ConsentScope

if TYPE_CHECKING:
    from app.models.contact import Contact


class Consent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "consents"

    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[ConsentChannel] = mapped_column(SQLEnum(ConsentChannel, name="consent_channel"), nullable=False)
    scope: Mapped[ConsentScope] = mapped_column(SQLEnum(ConsentScope, name="consent_scope"), nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="telegram_bot")
    proof_text: Mapped[str | None] = mapped_column(String(500))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contact: Mapped["Contact"] = relationship(back_populates="consents")

