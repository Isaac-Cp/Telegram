from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class ExternalLead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_leads"

    source: Mapped[str] = mapped_column(String(50), nullable=False) # reddit, web, etc.
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    status: Mapped[str] = mapped_column(String(20), default="NEW") # NEW, PROCESSED, IGNORED
