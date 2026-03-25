import logging

from redis import Redis

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


def enqueue_follow_up_job(job_id: str) -> None:
    try:
        redis_client: Redis = get_redis_client()
        redis_client.lpush("follow_up_jobs", job_id)
    except Exception as exc:  # pragma: no cover - defensive logging path
        logger.warning("Failed to enqueue follow-up job %s: %s", job_id, exc)
