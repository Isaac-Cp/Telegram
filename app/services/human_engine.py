import asyncio
import logging
import random
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.group import Group
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Safety Limits (Master Prompt Step 16)
SAFE_LIMITS = {
    "group_join_daily": 2,
    "public_reply_daily": 5,
    "dm_daily": 10,
    "public_reply_hourly": 3,
    "dm_hourly": 2
}

# Cooldown Period (Module 4)
COOLDOWN_MINUTES = 60

class HumanBehaviorEngine:
    """
    MODULE 12 & 16 — HUMAN BEHAVIOR ENGINE & SAFETY LAYER
    Ensure the system behaves like a real human user and adheres to Telegram safety rules.
    """

    def __init__(self):
        self.settings = get_settings()
        self._cooldown_active: Dict[str, datetime] = {}

    async def authorize_action(self, action_type: str) -> bool:
        """
        All outgoing actions must pass through the Human Behavior Engine before execution.
        Check daily/hourly limits and cooldown status.
        """
        # 1. Check Cooldown
        if action_type in self._cooldown_active:
            if datetime.utcnow() < self._cooldown_active[action_type]:
                logger.warning(f"[SLIE Safety] cooldown activated: {action_type} - Active until {self._cooldown_active[action_type]}")
                return False
            else:
                del self._cooldown_active[action_type]

        # 2. Check Safety Limits
        with SessionLocal() as db:
            if not await self._check_safety_limits(db, action_type):
                logger.warning(f"[SLIE Safety] cooldown activated: {action_type} - Limit reached. Triggering cooldown.")
                self._cooldown_active[action_type] = datetime.utcnow() + timedelta(minutes=COOLDOWN_MINUTES)
                return False

        # 3. Apply Activity Distribution (Randomness)
        if random.random() < 0.1:
            delay = random.randint(5 * 60, 15 * 60) # 5-15 min delay
            logger.info(f"[SLIE Human Engine] delay applied: {action_type} - Random distribution delay: {delay // 60} minutes")
            await asyncio.sleep(delay)
            
        return True

    async def _check_safety_limits(self, db: Session, action_type: str) -> bool:
        """
        Define maximum safe limits for each account (Master Prompt Step 16).
        """
        today = date.today()
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        if action_type == "group_join":
            count = db.query(func.count(Group.id)).filter(
                Group.joined == True,
                func.date(Group.updated_at) == today
            ).scalar() or 0
            return count < SAFE_LIMITS["group_join_daily"]
            
        elif action_type == "public_reply":
            # Daily check
            daily_count = db.query(func.count(Lead.id)).filter(
                Lead.public_reply_sent == True,
                func.date(Lead.updated_at) == today
            ).scalar() or 0
            if daily_count >= SAFE_LIMITS["public_reply_daily"]:
                return False
            
            # Hourly check
            hourly_count = db.query(func.count(Lead.id)).filter(
                Lead.public_reply_sent == True,
                Lead.updated_at >= one_hour_ago
            ).scalar() or 0
            return hourly_count < SAFE_LIMITS["public_reply_hourly"]
            
        elif action_type == "dm":
            # Daily check
            daily_count = db.query(func.count(Lead.id)).filter(
                Lead.dm_sent == True,
                func.date(Lead.last_contact) == today
            ).scalar() or 0
            if daily_count >= SAFE_LIMITS["dm_daily"]:
                return False
            
            # Hourly check
            hourly_count = db.query(func.count(Lead.id)).filter(
                Lead.dm_sent == True,
                Lead.last_contact >= one_hour_ago
            ).scalar() or 0
            return hourly_count < SAFE_LIMITS["dm_hourly"]
            
        return True

    async def apply_randomized_delay(self, action_type: str):
        """
        All actions must include random delays within defined ranges (Master Prompt Step 12).
        """
        # Define ranges (min_sec, max_sec)
        delays = {
            "group_join": (300, 1800), # 5-30 min
            "public_reply": (600, 1200), # 10-20 min
            "dm": (900, 2700), # 15-45 min
            "message_reply": (5, 20) # 5-20 sec for typing
        }
        
        min_sec, max_sec = delays.get(action_type, (60, 300))
        delay = random.randint(min_sec, max_sec)
        
        logger.info(f"[SLIE Human Engine] delay applied: {action_type} - {delay // 60} minutes ({delay}s)")
        await asyncio.sleep(delay)

    def is_within_natural_active_hours(self) -> bool:
        """
        Ensure actions occur throughout the day rather than in bursts.
        Active windows: 10:00–14:00 and 18:00–22:00.
        """
        now = datetime.now().time()
        # Using a simple check for realism
        morning_window = (time(10, 0) <= now <= time(14, 0))
        evening_window = (time(18, 0) <= now <= time(22, 0))
        
        if not (morning_window or evening_window):
            logger.info(f"[SLIE Human Engine] Outside natural active hours. Activity suspended.")
            return False
        return True

    async def simulate_human_typing(self, client, chat_id, text_length: int = 50):
        """
        Simulate typing speed based on message length.
        Avg typing speed: 40-60 wpm -> ~4-5 chars/sec
        """
        typing_time = max(3, min(10, text_length / 5))
        logger.info(f"[SLIE Human Engine] Simulating human typing for {typing_time:.1f}s...")
        try:
            async with client.action(chat_id, 'typing'):
                await asyncio.sleep(typing_time)
        except Exception as e:
            logger.error(f"[SLIE Human Engine] Error simulating typing: {e}")
            await asyncio.sleep(typing_time)

human_engine = HumanBehaviorEngine()
