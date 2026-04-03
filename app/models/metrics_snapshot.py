from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MetricsSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metrics_snapshots"

    day: Mapped[date] = mapped_column(Date, unique=True, index=True, nullable=False)
    contacts_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_conversations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_tickets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inbound_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outbound_messages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    follow_ups_due: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

