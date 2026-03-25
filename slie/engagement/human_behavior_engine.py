import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Optional
from slie.core.config import get_settings

logger = logging.getLogger(__name__)

class HumanBehaviorEngine:
    """
    STEP 12: HUMAN BEHAVIOR ENGINE
    All actions must pass through this engine.
    Apply random delays and enforce daily limits.
    
    STEP 16: SYSTEM SAFETY LAYER
    Implement risk controls and automatic cooldowns.
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
        self.action_history: Dict[str, list] = {
            "group_join": [],
            "public_reply": [],
            "dm": []
        }

    async def authorize_action(self, action_type: str) -> bool:
        """
        Authorize an action based on safety limits and apply random delays.
        """
        if action_type not in self.LIMITS:
            logger.error(f"[SLIE Safety] Unknown action type: {action_type}")
            return False

        # 1. Clean up old history
        self._cleanup_history(action_type)

        # 2. Check Daily and Hourly Limits (Step 16)
        daily_count = len([t for t in self.action_history[action_type] if t > datetime.utcnow() - timedelta(days=1)])
        hourly_count = len([t for t in self.action_history[action_type] if t > datetime.utcnow() - timedelta(hours=1)])

        if daily_count >= self.LIMITS[action_type]["daily"]:
            logger.warning(f"[SLIE Safety] cooldown activated: {action_type} - Daily limit reached.")
            return False
        
        if hourly_count >= self.LIMITS[action_type]["hourly"]:
            logger.warning(f"[SLIE Safety] cooldown activated: {action_type} - Hourly limit reached.")
            return False

        # 3. Apply Random Delay (Step 12)
        min_delay, max_delay = self.DELAYS[action_type]
        delay_minutes = random.randint(min_delay, max_delay)
        logger.info(f"[SLIE Human Engine] message scheduled: {action_type} delayed by {delay_minutes} minutes.")
        
        # In a real system, we might use a task queue for this delay.
        # For MVP, we'll simulate the wait if it's a blocking call or just log it.
        # await asyncio.sleep(delay_minutes * 60) 
        
        # 4. Record Action
        self.action_history[action_type].append(datetime.utcnow())
        return True

    def _cleanup_history(self, action_type: str):
        """Remove timestamps older than 24 hours."""
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        self.action_history[action_type] = [t for t in self.action_history[action_type] if t > one_day_ago]

human_engine = HumanBehaviorEngine()
