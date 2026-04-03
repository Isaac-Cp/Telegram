import logging
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import async_engine

logger = logging.getLogger(__name__)


async def get_readiness_report() -> tuple[dict[str, Any], int]:
    settings = get_settings()
    report: dict[str, Any] = {
        "status": "ready",
        "version": settings.version,
        "environment": settings.environment,
        "checks": {},
    }

    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        report["checks"]["database"] = "ok"
    except Exception as exc:
        logger.exception("Readiness check failed while verifying the database: %s", exc)
        report["status"] = "unready"
        report["checks"]["database"] = "error"
        report["error"] = "database_unavailable"
        return report, 503

    return report, 200
