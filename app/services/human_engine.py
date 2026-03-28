import asyncio
import logging
import random
from datetime import datetime, date, time as dt_time, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.group import Group
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Safety Limits (Master Prompt Step 16) - Adjusted per User Request
SAFE_LIMITS = {
    "group_join_daily": 2,
    "public_reply_daily": 15,
    "dm_daily": 3,
    "public_reply_hourly": 5,
    "dm_hourly": 1
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
        Elite Module 4 & 16: Ensure actions occur during active windows.
        Fully Autonomous Mode: If ENVIRONMENT is development or production,
        we use the configured BUSINESS_HOURS or allow 24/7 if not specified.
        """
        # If the user wants fully autonomous, we check if they've specified hours
        try:
            start_h = int(getattr(self.settings, "business_hours_start", 0))
            end_h = int(getattr(self.settings, "business_hours_end", 23))
        except:
            start_h, end_h = 0, 23 # Default to 24/7 if not configured

        # If 0-23, it's 24/7
        if start_h == 0 and end_h == 23:
            return True

        now = datetime.now().time()
        # Handle overnight hours
        if start_h <= end_h:
            is_active = (dt_time(hour=start_h, minute=0) <= now <= dt_time(hour=end_h, minute=59, second=59))
        else:
            is_active = (now >= dt_time(hour=start_h, minute=0) or now <= dt_time(hour=end_h, minute=59, second=59))
        
        if not is_active:
            logger.info(f"[SLIE Human Engine] Outside configured active hours ({start_h}:00 - {end_h}:00). Current: {now}")
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
