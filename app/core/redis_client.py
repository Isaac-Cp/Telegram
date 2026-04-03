import logging
import redis.asyncio as redis
from typing import Any, Dict, Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class MockRedis:
    """A simple in-memory mock for Redis when it's not available."""
    def __init__(self, *, warn: bool = True):
        self._data: Dict[str, Any] = {}
        log = logger.warning if warn else logger.info
        log("[SLIE Redis] Using In-Memory Mock Redis. Data will be lost on restart.")

    async def get(self, name: str) -> Optional[str]:
        return self._data.get(name)

    async def set(self, name: str, value: str, ex: Optional[int] = None, px: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        if nx and name in self._data: return False
        if xx and name not in self._data: return False
        self._data[name] = str(value)
        return True

    async def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self._data:
                del self._data[name]
                count += 1
        return count

    async def ping(self) -> bool:
        return True

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class RedisClient:
    def __init__(self):
        self.settings = get_settings()
        self._redis: Any = None

    async def connect(self):
        """
        Initialize Redis connection and validate it.
        """
        self.settings = get_settings()

        if not (self.settings.background_workers_enabled or self.settings.redis_required):
            logger.info("Redis connection skipped because this service does not require Redis.")
            self._redis = MockRedis(warn=False)
            return

        try:
            self._redis = redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=self.settings.redis_connect_timeout_seconds,
                socket_timeout=self.settings.redis_connect_timeout_seconds,
                health_check_interval=30,
            )
            # Validate connection
            await self._redis.ping()
            logger.info(f"Connected to Redis at {self.settings.redis_url}")
        except Exception as e:
            if self.settings.redis_required:
                logger.exception("Failed to connect to required Redis instance: %s", e)
                raise

            logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory mock.")
            self._redis = MockRedis()

    async def disconnect(self):
        if self._redis:
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:
                await self._redis.close()
            logger.info("Redis connection closed.")

    @property
    def client(self) -> Any:
        if self._redis is None:
            # If connect hasn't been called, return a mock instead of raising error
            self._redis = MockRedis()
        return self._redis

redis_client = RedisClient()
