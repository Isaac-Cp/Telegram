import asyncio
import inspect
import logging
import os
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
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
    slie_reddit_discovery,
    slie_power_upgrades,
    slie_score_decay,
    cleanup_database,
)


def retryable_job(label, fn, max_retries=3, shutdown_on_failure=False):
    if inspect.iscoroutinefunction(fn):
        async def wrapper(*args, **kwargs):
            delay = 2
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    logger.error(f"{label} failed (attempt {attempt}/{max_retries}): {exc}")
                    if attempt == max_retries:
                        break
                    await asyncio.sleep(delay)
                    delay = min(30, delay * 2)
            logger.critical(f"{label} failed after {max_retries} attempts.")
            if shutdown_on_failure:
                os._exit(1)
            raise last_exc
        return wrapper

    def wrapper(*args, **kwargs):
        delay = 2
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                logger.error(f"{label} failed (attempt {attempt}/{max_retries}): {exc}")
                if attempt == max_retries:
                    break
                time.sleep(delay)
                delay = min(30, delay * 2)
        logger.critical(f"{label} failed after {max_retries} attempts.")
        if shutdown_on_failure:
            os._exit(1)
        raise last_exc
    return wrapper


settings = get_settings()
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)

scheduler.add_job(retryable_job("queue_due_follow_ups", queue_due_follow_ups), "interval", minutes=5, id="queue_due_follow_ups", replace_existing=True)
scheduler.add_job(retryable_job("cancel_revoked_follow_ups", cancel_revoked_follow_ups), "interval", minutes=5, id="cancel_revoked_follow_ups", replace_existing=True)
scheduler.add_job(retryable_job("refresh_engagement_scores", refresh_engagement_scores), "interval", minutes=15, id="refresh_engagement_scores", replace_existing=True)
scheduler.add_job(retryable_job("close_stale_conversations", close_stale_conversations), "interval", hours=1, id="close_stale_conversations", replace_existing=True)
scheduler.add_job(retryable_job("snapshot_daily_metrics", snapshot_daily_metrics), "cron", hour=23, minute=55, id="snapshot_daily_metrics", replace_existing=True)

# SLIE Discovery Engine Jobs - Accelerated for session
scheduler.add_job(retryable_job("slie_keyword_discovery", slie_keyword_discovery), "interval", minutes=10, id="slie_keyword_discovery", replace_existing=True)
scheduler.add_job(retryable_job("slie_group_analysis", slie_group_analysis), "interval", minutes=10, id="slie_group_analysis", replace_existing=True)
scheduler.add_job(retryable_job("slie_join_scheduler", slie_join_scheduler), "interval", minutes=10, id="slie_join_scheduler", replace_existing=True)
scheduler.add_job(retryable_job("slie_ltv_recalculation", slie_ltv_recalculation), "interval", hours=24, id="slie_ltv_recalculation", replace_existing=True)

# SLIE Messaging Jobs
scheduler.add_job(retryable_job("slie_public_replies", slie_public_replies), "interval", minutes=2, id="slie_public_replies", replace_existing=True)
scheduler.add_job(retryable_job("slie_private_dms", slie_private_dms), "interval", minutes=2, id="slie_private_dms", replace_existing=True)
scheduler.add_job(retryable_job("slie_reddit_discovery", slie_reddit_discovery), "interval", hours=1, id="slie_reddit_discovery", replace_existing=True)
scheduler.add_job(retryable_job("slie_power_upgrades", slie_power_upgrades), "interval", minutes=30, id="slie_power_upgrades", replace_existing=True)
scheduler.add_job(retryable_job("slie_score_decay", slie_score_decay), "interval", hours=24, id="slie_score_decay", replace_existing=True)

# Database cleanup job
scheduler.add_job(retryable_job("cleanup_database", cleanup_database), "cron", hour=3, minute=0, id="database_cleanup", replace_existing=True)

