from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.dashboard import DashboardSettingsPayload, _load_settings, _save_settings
from app.db.base import Base
from app.models.dashboard_setting import DashboardSetting


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DashboardSetting.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def test_dashboard_settings_are_persisted_in_database():
    db = make_session()

    saved = _save_settings(
        db,
        DashboardSettingsPayload(
            target_tags=[" IPTV ", "iptv", "reseller"],
            search_tags=["buffering"],
            brand_tags=["SLIE"],
            watch_terms=["competitor"],
            lead_score_threshold=130,
            daily_dm_limit=-4,
            auto_join_groups=True,
            telegram_outreach_enabled=True,
            notes="  Production tuning  ",
        ),
    )
    loaded = _load_settings(db)

    assert saved["target_tags"] == ["IPTV", "reseller"]
    assert loaded["target_tags"] == ["IPTV", "reseller"]
    assert loaded["lead_score_threshold"] == 100
    assert loaded["daily_dm_limit"] == 0
    assert loaded["auto_join_groups"] is True
    assert loaded["telegram_outreach_enabled"] is True
    assert loaded["notes"] == "Production tuning"
