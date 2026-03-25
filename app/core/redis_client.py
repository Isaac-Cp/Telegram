import logging
import redis.asyncio as redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.settings = get_settings()
        self._redis: redis.Redis | None = None

    async def connect(self):
        """
        Initialize Redis connection and validate it.
        """
        try:
            self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
            # Validate connection
            await self._redis.ping()
            logger.info(f"Connected to Redis at {self.settings.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis = None
            raise ConnectionError(f"Could not connect to Redis: {e}")

    async def disconnect(self):
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed.")

    @property
    def client(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._redis

redis_client = RedisClient()
