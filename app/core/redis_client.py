import fnmatch
import logging
import time
import redis.asyncio as redis
from typing import Any, Dict, Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class MockRedis:
    """A simple in-memory mock for Redis when it's not available."""
    def __init__(self):
        # store: key -> (value:str, expire_ts: int|None)
        self._data: Dict[str, tuple[Any, int | None]] = {}
        logger.warning("[SLIE Redis] Using In-Memory Mock Redis. Data will be lost on restart.")

    async def get(self, name: str) -> Optional[str]:
        entry = self._data.get(name)
        if not entry:
            return None
        value, expire = entry
        if expire is not None and expire < int(time.time()):
            del self._data[name]
            return None
        return value

    async def set(self, name: str, value: str, ex: Optional[int] = None, px: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        now = int(time.time())
        if nx and name in self._data:
            # check expiry
            existing = self._data.get(name)
            if existing:
                _, expire = existing
                if expire is None or expire >= now:
                    return False
        if xx and name not in self._data:
            return False
        
        # Use px (milliseconds) if provided and ex is not
        if px and not ex:
            expire_ts = now + (px // 1000)
        else:
            expire_ts = now + ex if ex else None
            
        self._data[name] = (str(value), expire_ts)
        return True

    async def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            entry = self._data.get(name)
            if entry:
                del self._data[name]
                count += 1
        return count

    async def ping(self) -> bool:
        return True

    async def keys(self, pattern: str) -> list[str]:
        return [key for key in self._data.keys() if fnmatch.fnmatch(key, pattern)]

    async def incr(self, name: str) -> int:
        now = int(time.time())
        entry = self._data.get(name)
        if not entry:
            self._data[name] = ("1", None)
            return 1
        value, expire = entry
        if expire is not None and expire < now:
            self._data[name] = ("1", None)
            return 1
        try:
            new_val = int(value) + 1
        except Exception:
            new_val = 1
        self._data[name] = (str(new_val), expire)
        return new_val

    async def expire(self, name: str, seconds: int) -> bool:
        entry = self._data.get(name)
        if not entry:
            return False
        value, _ = entry
        self._data[name] = (value, int(time.time()) + int(seconds))
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
        try:
            self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
            # Validate connection
            await self._redis.ping()
            logger.info("[SLIE Redis] Connected successfully to %s", self.settings.redis_url)
        except Exception as e:
            if self.settings.environment == "production":
                logger.critical("[SLIE Redis] CRITICAL: Could not connect to real Redis in production: %s", e)
                raise RuntimeError(f"Real Redis is mandatory in production environment. Error: {e}")
            
            logger.warning("[SLIE Redis] Could not connect to real Redis: %s. Falling back to Mock.", e)
            self._redis = MockRedis()

    @property
    def client(self) -> Any:
        if self._redis is None:
            if self.settings.environment == "production":
                raise RuntimeError("Redis client accessed before a real production Redis connection was established.")
            # Fallback for synchronous or early access. Keep one mock instance so
            # cache data survives across calls in local/dev verification.
            self._redis = MockRedis()
        return self._redis

    async def disconnect(self):
        if self._redis and hasattr(self._redis, "close"):
            await self._redis.close()

redis_client = RedisClient()
