from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import LifecycleStage

if TYPE_CHECKING:
    from app.models.contact import Contact


class LeadProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_profiles"

    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), unique=True, index=True)
    lifecycle_stage: Mapped[LifecycleStage] = mapped_column(
        SQLEnum(LifecycleStage, name="lifecycle_stage"),
        default=LifecycleStage.NEW,
        nullable=False,
    )
    engagement_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contact: Mapped["Contact"] = relationship(back_populates="lead_profile")

