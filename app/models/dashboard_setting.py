from typing import Any

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DashboardSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dashboard_settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_dashboard_settings_key"),
        Index("ix_dashboard_settings_key", "key", unique=True),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
