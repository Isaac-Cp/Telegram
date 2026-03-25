import asyncio
import logging
import random
from datetime import datetime, time
from typing import List

from telethon import functions, types

from app.core.config import get_settings
from app.services.telegram_client import telegram_client_manager

logger = logging.getLogger(__name__)

class AntiBanBehaviorEngine:
    def __init__(self):
        self.settings = get_settings()

    async def simulate_human_activity(self):
        """Simulate human-like behavior to prevent bans."""
        client = await telegram_client_manager.get_client()
        
        # Randomly update online status
        await client(functions.account.UpdateStatusRequest(offline=False))
        logger.info("Simulated online status update.")

        # Randomly perform typing action in a joined group
        # (Wait for random group messages)
        
        # Check active hours (e.g., 9 AM to 10 PM)
        now = datetime.utcnow().time()
        start_time = time(self.settings.business_hours_start, 0)
        end_time = time(self.settings.business_hours_end, 0)
        
        if not (start_time <= now <= end_time):
            logger.info("Outside of active hours. Sleeping...")
            return False
            
        return True

    async def get_typing_delay(self, text: str) -> float:
        """Calculate typing delay based on message length."""
        # Humans type at ~40-60 wpm.
        # ~5 chars per word -> ~200-300 cpm.
        # Delay = len(text) / (cpm / 60)
        chars_per_second = random.uniform(3, 5)
        return len(text) / chars_per_second

    async def check_if_admin(self, chat_id: int, user_id: int) -> bool:
        """Check if a user is an admin in a group."""
        client = await telegram_client_manager.get_client()
        try:
            permissions = await client.get_permissions(chat_id, user_id)
            return permissions.is_admin
        except Exception as e:
            logger.error(f"Error checking admin permissions: {e}")
            return False

anti_ban_behavior_engine = AntiBanBehaviorEngine()
