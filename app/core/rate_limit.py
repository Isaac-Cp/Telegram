from functools import lru_cache

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


@lru_cache
def get_limiter() -> Limiter:
    import os
    settings = get_settings()
    
    # In development, use memory storage if redis is not explicitly required or available
    storage_uri = settings.redis_url
    if settings.environment == "development" or os.getenv("DEVELOPMENT", "").lower() == "true":
        # Fallback to memory storage for local development to avoid Redis dependency errors
        storage_uri = "memory://"
        
    return Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=[f"{settings.rate_limit_requests_per_minute}/minute"],
        headers_enabled=True,
    )
