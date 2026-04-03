import asyncio
import importlib
import sys


def _load_health_checks(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test_health_checks.sqlite")
    monkeypatch.setenv("BACKGROUND_WORKERS_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")

    for module_name in [
        "app.core.health_checks",
        "app.db.session",
        "app.core.config",
        "app.core.env_loader",
    ]:
        sys.modules.pop(module_name, None)

    return importlib.import_module("app.core.health_checks")


class _HealthyConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _query):
        return 1


class _HealthyEngine:
    def connect(self):
        return _HealthyConnection()


class _BrokenConnection:
    async def __aenter__(self):
        raise RuntimeError("database offline")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _BrokenEngine:
    def connect(self):
        return _BrokenConnection()


def test_readiness_report_returns_200_when_database_is_available(monkeypatch):
    health_checks = _load_health_checks(monkeypatch)
    monkeypatch.setattr(health_checks, "async_engine", _HealthyEngine())

    report, status_code = asyncio.run(health_checks.get_readiness_report())

    assert status_code == 200
    assert report["status"] == "ready"
    assert report["checks"]["database"] == "ok"


def test_readiness_report_returns_503_when_database_is_unavailable(monkeypatch):
    health_checks = _load_health_checks(monkeypatch)
    monkeypatch.setattr(health_checks, "async_engine", _BrokenEngine())

    report, status_code = asyncio.run(health_checks.get_readiness_report())

    assert status_code == 503
    assert report["status"] == "unready"
    assert report["checks"]["database"] == "error"
