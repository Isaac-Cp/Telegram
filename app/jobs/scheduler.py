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
)

settings = get_settings()

scheduler = AsyncIOScheduler(
    timezone=settings.timezone,
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 300,
    },
)
scheduler.add_job(queue_due_follow_ups, "interval", minutes=5, id="queue_due_follow_ups", replace_existing=True)
scheduler.add_job(cancel_revoked_follow_ups, "interval", minutes=5, id="cancel_revoked_follow_ups", replace_existing=True)
scheduler.add_job(refresh_engagement_scores, "interval", minutes=15, id="refresh_engagement_scores", replace_existing=True)
scheduler.add_job(close_stale_conversations, "interval", hours=1, id="close_stale_conversations", replace_existing=True)
scheduler.add_job(snapshot_daily_metrics, "cron", hour=23, minute=55, id="snapshot_daily_metrics", replace_existing=True)

# SLIE Discovery Engine Jobs
scheduler.add_job(slie_keyword_discovery, "interval", hours=6, id="slie_keyword_discovery", replace_existing=True)
scheduler.add_job(slie_group_analysis, "interval", hours=12, id="slie_group_analysis", replace_existing=True)
scheduler.add_job(slie_join_scheduler, "interval", hours=1, id="slie_join_scheduler", replace_existing=True)
scheduler.add_job(slie_ltv_recalculation, "interval", hours=24, id="slie_ltv_recalculation", replace_existing=True)

# SLIE Messaging Jobs
scheduler.add_job(
    slie_public_replies,
    "interval",
    minutes=settings.scheduler_public_reply_interval_minutes,
    id="slie_public_replies",
    replace_existing=True,
)
scheduler.add_job(
    slie_private_dms,
    "interval",
    minutes=settings.scheduler_private_dm_interval_minutes,
    id="slie_private_dms",
    replace_existing=True,
)
scheduler.add_job(
    slie_reddit_discovery,
    "interval",
    hours=settings.scheduler_reddit_interval_hours,
    id="slie_reddit_discovery",
    replace_existing=True,
)
scheduler.add_job(
    slie_power_upgrades,
    "interval",
    minutes=settings.scheduler_power_upgrades_interval_minutes,
    id="slie_power_upgrades",
    replace_existing=True,
)
