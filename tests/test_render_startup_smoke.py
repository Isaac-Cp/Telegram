import importlib
import sys

from fastapi.testclient import TestClient


def test_render_style_startup_succeeds_with_fresh_database(monkeypatch, tmp_path):
    db_path = tmp_path / "render_startup.sqlite"

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.resolve().as_posix()}")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "true")
    monkeypatch.setenv("BACKGROUND_WORKERS_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    monkeypatch.setenv("REDIS_REQUIRED", "false")
    monkeypatch.setenv("SENTRY_DSN", "")

    for module_name in [
        "app.main",
        "app.api.routes.health",
        "app.core.health_checks",
        "app.core.redis_client",
        "app.core.migrations",
        "app.db.db_init",
        "app.db.session",
        "app.core.config",
        "app.core.env_loader",
    ]:
        sys.modules.pop(module_name, None)

    app_module = importlib.import_module("app.main")

    with TestClient(app_module.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        assert client.get("/api/v1/health/").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 200
        assert client.get("/api/v1/dashboard/").status_code == 200
