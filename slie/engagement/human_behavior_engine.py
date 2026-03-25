import asyncio
import logging
import random
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import redis.asyncio as redis
from slie.core.config import get_settings

logger = logging.getLogger(__name__)

class HumanBehaviorEngine:
    """
    STEP 12: HUMAN BEHAVIOR ENGINE
    All actions must pass through this engine.
    Apply random delays and enforce daily limits.
    
    STEP 16: SYSTEM SAFETY LAYER
    Implement risk controls and automatic cooldowns using Redis.
    """
    
    LIMITS = {
        "group_join": {"daily": 2, "hourly": 1},
        "public_reply": {"daily": 5, "hourly": 3},
        "dm": {"daily": 10, "hourly": 2}
    }

    DELAYS = {
        "group_join": (5, 30), # minutes
        "public_reply": (10, 20), # minutes
        "dm": (15, 45) # minutes
    }

    def __init__(self):
        self.settings = get_settings()
        self.redis: Optional[redis.Redis] = None
        self._in_memory_history: Dict[str, List[float]] = {
            "group_join": [],
            "public_reply": [],
            "dm": []
        }

    async def _get_redis(self):
        if self.redis is None:
            try:
                self.redis = redis.from_url(self.settings.redis_url, decode_responses=True)
                await self.redis.ping()
            except Exception as e:
                logger.warning(f"[SLIE Safety] Redis connection failed, falling back to in-memory: {e}")
                self.redis = False # Mark as failed
        return self.redis if self.redis is not False else None

    async def authorize_action(self, action_type: str) -> bool:
        """
        Authorize an action based on safety limits and apply random delays.
        """
        if action_type not in self.LIMITS:
            logger.error(f"[SLIE Safety] Unknown action type: {action_type}")
            return False

        r = await self._get_redis()
        now_ts = datetime.utcnow().timestamp()

        # 1. Retrieve history
        if r:
            key = f"slie:safety:{action_type}"
            history_json = await r.get(key)
            history = json.loads(history_json) if history_json else []
        else:
            history = self._in_memory_history[action_type]

        # 2. Cleanup old history (Step 16)
        one_day_ago = now_ts - 86400
        history = [t for t in history if t > one_day_ago]

        # 3. Check Daily and Hourly Limits
        daily_count = len(history)
        one_hour_ago = now_ts - 3600
        hourly_count = len([t for t in history if t > one_hour_ago])

        if daily_count >= self.LIMITS[action_type]["daily"]:
            logger.warning(f"[SLIE Safety] cooldown activated: {action_type} - Daily limit reached ({daily_count}).")
            return False
        
        if hourly_count >= self.LIMITS[action_type]["hourly"]:
            logger.warning(f"[SLIE Safety] cooldown activated: {action_type} - Hourly limit reached ({hourly_count}).")
            return False

        # 4. Apply Random Delay (Step 12)
        min_delay, max_delay = self.DELAYS[action_type]
        delay_minutes = random.randint(min_delay, max_delay)
        logger.info(f"[SLIE Engagement] message scheduled: {action_type} delayed by {delay_minutes} minutes.")
        
        # 5. Record Action
        history.append(now_ts)
        if r:
            await r.set(f"slie:safety:{action_type}", json.dumps(history), ex=86400)
        else:
            self._in_memory_history[action_type] = history

        return True

human_engine = HumanBehaviorEngine()
