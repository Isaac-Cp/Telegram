from app.core.config import Settings


def make_production_settings(**overrides):
    data = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://slie:secret@db.example.com:5432/slie",
        "redis_url": "redis://redis.example.com:6379/0",
        "secret_key": "x" * 48,
        "dashboard_admin_password": "strong-dashboard-password",
        "dashboard_control_password": "strong-control-password",
        "trusted_origins": "https://dashboard.example.com",
        "trusted_hosts": "",
        "telegram_api_id": 12345,
        "telegram_api_hash": "hash",
        "telegram_phone": "+10000000000",
    }
    data.update(overrides)
    return Settings(**data)


def test_production_settings_reject_default_secrets():
    settings = make_production_settings(
        secret_key="super-secret-key-change-in-production",
        dashboard_admin_password="changeme",
        dashboard_control_password="control-changeme",
    )

    issues = settings.production_issues()

    assert any("SECRET_KEY" in issue for issue in issues)
    assert any("DASHBOARD" in issue for issue in issues)


def test_production_settings_derive_trusted_hosts_from_origins():
    settings = make_production_settings(trusted_hosts="")

    assert settings.trusted_hosts_list == ["dashboard.example.com"]
    assert settings.production_issues() == []


def test_production_settings_reject_placeholders_and_local_hosts():
    settings = make_production_settings(
        database_url="postgresql+asyncpg://postgres:postgres@postgres:5432/slie_db",
        secret_key="replace-with-a-strong-32-plus-character-secret",
        dashboard_admin_password="replace-with-a-strong-dashboard-password",
        dashboard_control_password="replace-with-a-strong-control-password",
        redis_url="redis://localhost:6379/0",
        trusted_origins="http://localhost:8000",
        trusted_hosts="localhost,127.0.0.1",
    )

    issues = settings.production_issues()

    assert any("SECRET_KEY" in issue for issue in issues)
    assert any("DASHBOARD" in issue for issue in issues)
    assert any("DASHBOARD_CONTROL" in issue for issue in issues)
    assert any("DATABASE_URL" in issue for issue in issues)
    assert any("REDIS_URL" in issue for issue in issues)
    assert any("TRUSTED_ORIGINS" in issue for issue in issues)
    assert any("TRUSTED_HOSTS" in issue for issue in issues)
