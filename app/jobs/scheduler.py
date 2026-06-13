import asyncio
import logging
import os
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.core.config import get_settings
from app.db.session import engine
from app.jobs.tasks import (
    cancel_revoked_follow_ups,
    close_stale_conversations,
    queue_due_follow_ups,
    refresh_engagement_scores,
    snapshot_daily_metrics,
    slie_keyword_discovery,
    slie_group_analysis,
    slie_join_scheduler,
    slie_ltv_recalculation,
    slie_public_replies,
    slie_private_dms,
    slie_performance_brain,
    slie_reddit_discovery,
    slie_power_upgrades,
    slie_score_decay,
    cleanup_database,
)


settings = get_settings()
logger = logging.getLogger(__name__)

def _raise_after_retries(label: str, last_exc: Exception | None, shutdown_on_failure: bool) -> None:
    logger.critical("%s failed after retries.", label)
    if shutdown_on_failure and os.getenv("ENVIRONMENT") == "production":
        logger.critical("Escalating critical failure. Application state may be degraded.")
    if last_exc is not None:
        raise last_exc


async def _run_async_job(label: str, fn, max_retries: int = 3, shutdown_on_failure: bool = False):
    delay = 2
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            logger.error("%s failed (attempt %s/%s): %s", label, attempt, max_retries, exc)
            if attempt == max_retries:
                break
            await asyncio.sleep(delay)
            delay = min(30, delay * 2)
    _raise_after_retries(label, last_exc, shutdown_on_failure)


def _run_sync_job(label: str, fn, max_retries: int = 3, shutdown_on_failure: bool = False):
    delay = 2
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            logger.error("%s failed (attempt %s/%s): %s", label, attempt, max_retries, exc)
            if attempt == max_retries:
                break
            time.sleep(delay)
            delay = min(30, delay * 2)
    _raise_after_retries(label, last_exc, shutdown_on_failure)


def run_queue_due_follow_ups():
    return _run_sync_job("queue_due_follow_ups", queue_due_follow_ups)


def run_cancel_revoked_follow_ups():
    return _run_sync_job("cancel_revoked_follow_ups", cancel_revoked_follow_ups)


def run_refresh_engagement_scores():
    return _run_sync_job("refresh_engagement_scores", refresh_engagement_scores)


def run_close_stale_conversations():
    return _run_sync_job("close_stale_conversations", close_stale_conversations)


def run_snapshot_daily_metrics():
    return _run_sync_job("snapshot_daily_metrics", snapshot_daily_metrics)


def run_slie_performance_brain():
    return _run_sync_job("slie_performance_brain", slie_performance_brain)


async def run_slie_keyword_discovery():
    return await _run_async_job("slie_keyword_discovery", slie_keyword_discovery)


async def run_slie_group_analysis():
    return await _run_async_job("slie_group_analysis", slie_group_analysis)


async def run_slie_join_scheduler():
    return await _run_async_job("slie_join_scheduler", slie_join_scheduler)


async def run_slie_ltv_recalculation():
    return await _run_async_job("slie_ltv_recalculation", slie_ltv_recalculation)


async def run_slie_public_replies():
    return await _run_async_job("slie_public_replies", slie_public_replies)


async def run_slie_private_dms():
    return await _run_async_job("slie_private_dms", slie_private_dms)


async def run_slie_reddit_discovery():
    return await _run_async_job("slie_reddit_discovery", slie_reddit_discovery)


async def run_slie_power_upgrades():
    return await _run_async_job("slie_power_upgrades", slie_power_upgrades)


async def run_slie_score_decay():
    return await _run_async_job("slie_score_decay", slie_score_decay)


async def run_cleanup_database():
    return await _run_async_job("cleanup_database", cleanup_database)


# Module 16: Persistent Job Stores for Horizontal Scaling
jobstores = {
    "default": SQLAlchemyJobStore(engine=engine)
}
job_defaults = {
    "coalesce": True,
    "max_instances": 1,
    "misfire_grace_time": 300
}

scheduler = AsyncIOScheduler(
    timezone=settings.timezone,
    jobstores=jobstores,
    job_defaults=job_defaults
)

scheduler.add_job(run_queue_due_follow_ups, "interval", minutes=5, id="queue_due_follow_ups", replace_existing=True)
scheduler.add_job(run_cancel_revoked_follow_ups, "interval", minutes=5, id="cancel_revoked_follow_ups", replace_existing=True)
scheduler.add_job(run_refresh_engagement_scores, "interval", minutes=15, id="refresh_engagement_scores", replace_existing=True)
scheduler.add_job(run_close_stale_conversations, "interval", hours=1, id="close_stale_conversations", replace_existing=True)
scheduler.add_job(run_snapshot_daily_metrics, "cron", hour=23, minute=55, id="snapshot_daily_metrics", replace_existing=True)
scheduler.add_job(run_slie_performance_brain, "interval", minutes=30, id="slie_performance_brain", replace_existing=True)

if settings.telegram_enabled:
    # SLIE Discovery Engine Jobs - Accelerated for session
    scheduler.add_job(run_slie_keyword_discovery, "interval", minutes=10, id="slie_keyword_discovery", replace_existing=True)
    scheduler.add_job(run_slie_group_analysis, "interval", minutes=10, id="slie_group_analysis", replace_existing=True)
    scheduler.add_job(run_slie_join_scheduler, "interval", minutes=10, id="slie_join_scheduler", replace_existing=True)
    scheduler.add_job(run_slie_ltv_recalculation, "interval", hours=24, id="slie_ltv_recalculation", replace_existing=True)

    # SLIE Messaging Jobs
    scheduler.add_job(run_slie_public_replies, "interval", minutes=2, id="slie_public_replies", replace_existing=True)
    scheduler.add_job(run_slie_private_dms, "interval", minutes=2, id="slie_private_dms", replace_existing=True)
    scheduler.add_job(run_slie_reddit_discovery, "interval", hours=1, id="slie_reddit_discovery", replace_existing=True)
    scheduler.add_job(run_slie_power_upgrades, "interval", minutes=30, id="slie_power_upgrades", replace_existing=True)
    scheduler.add_job(run_slie_score_decay, "interval", hours=24, id="slie_score_decay", replace_existing=True)
else:
    logger.info("Telegram scheduler jobs not registered (TELEGRAM_ENABLED=false).")

# Database cleanup job
scheduler.add_job(run_cleanup_database, "cron", hour=3, minute=0, id="database_cleanup", replace_existing=True)

