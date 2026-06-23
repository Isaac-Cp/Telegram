from functools import lru_cache
import logging
from redis import Redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class MockRedisSync:
    def __init__(self):
        self._data = {}
        logger.warning("[SLIE Redis] Using Synchronous In-Memory Mock Redis.")

    def blpop(self, keys, timeout=0):
        return None

    def get(self, name):
        return self._data.get(name)

    def set(self, name, value, ex=None):
        self._data[name] = value
        return True

    def ping(self):
        return True

@lru_cache
def get_redis_client() -> Redis:
    settings = get_settings()
    if settings.redis_url.lower().startswith("memory://"):
        if settings.environment.lower() == "production":
            raise RuntimeError("memory:// Redis is not allowed in production.")
        logger.warning("[SLIE Redis] Using configured synchronous in-memory mock Redis.")
        return MockRedisSync()
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        if settings.environment.lower() == "production":
            raise RuntimeError(f"Real Redis is mandatory in production. Error: {e}") from e
        logger.error(f"Redis connection failed: {e}. Falling back to mock.")
        return MockRedisSync()
