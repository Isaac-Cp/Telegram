import logging
import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Dict
from sqlalchemy import func, select
from app.core.config import get_settings
from app.models.lead import Lead
from app.models.group import Group
from app.models.telegram_account import TelegramAccount

logger = logging.getLogger(__name__)

class SafetyController:
    """
    Centralized Safety Controller for rate-limiting and anti-ban protection.
    Consolidates logic from multiple services into a single source of truth.
    """
    def __init__(self):
        self.settings = get_settings()
        # Cooldown tracking (in-memory fallback, preferably in Redis)
        self._cooldowns: Dict[str, datetime] = {}
        self.limits = {
            "dm": {"daily": self.settings.max_dms_per_day, "hourly": 2},
            "public_reply": {"daily": self.settings.max_public_replies_per_day, "hourly": 5},
            "group_join": {"daily": self.settings.max_groups_join_per_day, "hourly": 2},
        }

    def is_action_safe(self, db, account_phone: str, action_type: str) -> bool:
        """
        Check if an action is safe to perform based on daily and hourly limits.
        """
        # 1. Check active cooldowns
        if self.is_in_cooldown(account_phone, action_type):
            logger.warning(f"[Safety Controller] {action_type} for {account_phone} is in cooldown.")
            return False

        # 2. Check limits from database (source of truth)
        account = db.execute(
            select(TelegramAccount).where(TelegramAccount.phone_number == account_phone)
        ).scalar_one_or_none()
        
        if not account:
            # Fallback to general check if account not in table
            return self._check_general_limits(db, action_type)

        if action_type == "dm":
            if account.daily_dm_count >= self.limits["dm"]["daily"]:
                return False
        elif action_type == "public_reply":
            if account.daily_reply_count >= self.limits["public_reply"]["daily"]:
                return False
        elif action_type == "group_join":
            if account.groups_joined >= self.limits["group_join"]["daily"]:
                return False

        return True

    def _check_general_limits(self, db, action_type: str) -> bool:
        """Fallback limit check using aggregate data."""
        from datetime import date
        today = date.today()
        if action_type == "group_join":
            count = db.query(func.count(Group.id)).filter(
                Group.joined == True,
                func.date(Group.updated_at) == today
            ).scalar() or 0
            return count < self.limits["group_join"]["daily"]
        elif action_type == "public_reply":
            count = db.query(func.count(Lead.id)).filter(
                Lead.public_reply_sent == True,
                func.date(Lead.updated_at) == today
            ).scalar() or 0
            return count < self.limits["public_reply"]["daily"]
        elif action_type == "dm":
            count = db.query(func.count(Lead.id)).filter(
                Lead.dm_sent == True,
                func.date(Lead.last_contact) == today
            ).scalar() or 0
            return count < self.limits["dm"]["daily"]
        return True

    def is_in_cooldown(self, account_phone: str, action_type: str) -> bool:
        key = f"{account_phone}:{action_type}"
        if key in self._cooldowns:
            if datetime.now(timezone.utc) < self._cooldowns[key]:
                return True
            else:
                del self._cooldowns[key]
        return False

    def trigger_cooldown(self, account_phone: str, action_type: str, minutes: int):
        key = f"{account_phone}:{action_type}"
        self._cooldowns[key] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        logger.info(f"[Safety Controller] Cooldown triggered for {key}: {minutes} minutes")

    async def apply_smart_delay(self, action_type: str):
        """Apply a randomized delay based on action type to mimic human behavior."""
        if action_type == "dm":
            delay = random.randint(self.settings.dm_delay_min_minutes * 60, self.settings.dm_delay_max_minutes * 60)
        elif action_type == "public_reply":
            delay = self.settings.public_reply_delay_minutes * 60
        else:
            delay = random.randint(10, 30)
        
        logger.info(f"[Safety Controller] Applying smart delay for {action_type}: {delay // 60}m {delay % 60}s")
        await asyncio.sleep(delay)

safety_controller = SafetyController()
