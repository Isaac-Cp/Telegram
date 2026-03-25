import logging
from datetime import datetime, timedelta
from typing import Optional
from telethon import functions, types, errors
from slie.telegram.telegram_client import telegram_engine
from slie.core.database import AsyncSessionLocal
from slie.models.group_models import Group
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

class GroupQualityFilter:
    """
    STEP 5: GROUP QUALITY FILTER
    Before joining any group analyze member count, message frequency, and posting permissions.
    """
    MIN_MEMBERS = 200
    MIN_MESSAGES_PER_DAY = 5

    async def analyze_group(self, telegram_id: int) -> bool:
        """
        Analyze group based on Step 5 criteria.
        Returns True if the group is valid for joining.
        """
        if not telegram_engine.client:
            return False

        try:
            # 1. Get detailed group info
            chat = await telegram_engine.client.get_entity(telegram_id)
            full_chat = await telegram_engine.client(functions.channels.GetFullChannelRequest(channel=chat))
            
            # Check Member Count
            member_count = full_chat.full_chat.participants_count
            if member_count < self.MIN_MEMBERS:
                logger.info(f"[SLIE Discovery] Rejecting group {chat.title}: Members {member_count} < {self.MIN_MEMBERS}")
                await self._update_group_status(telegram_id, "REJECTED_LOW_MEMBERS")
                return False

            # 2. Check Message Frequency (Last 24 hours)
            messages = await telegram_engine.client.get_messages(chat, limit=100)
            now = datetime.now(datetime.now().astimezone().tzinfo)
            day_ago = now - timedelta(days=1)
            
            msgs_last_24h = [m for m in messages if m.date > day_ago]
            if len(msgs_last_24h) < self.MIN_MESSAGES_PER_DAY:
                logger.info(f"[SLIE Discovery] Rejecting group {chat.title}: Msg freq {len(msgs_last_24h)} < {self.MIN_MESSAGES_PER_DAY}")
                await self._update_group_status(telegram_id, "REJECTED_LOW_ACTIVITY")
                return False

            # 3. Check Posting Permissions (if possible without joining)
            # This is hard to check perfectly without joining, but we can check if it's a broadcast channel
            if isinstance(chat, types.Channel) and chat.broadcast:
                logger.info(f"[SLIE Discovery] Rejecting group {chat.title}: Broadcast channel detected.")
                await self._update_group_status(telegram_id, "REJECTED_BROADCAST")
                return False

            # Group is valid
            logger.info(f"[SLIE Discovery] Group {chat.title} passed quality filter.")
            await self._update_group_status(telegram_id, "APPROVED", member_count=member_count)
            return True

        except Exception as e:
            logger.error(f"[SLIE Discovery] Error analyzing group {telegram_id}: {str(e)}")
            return False

    async def _update_group_status(self, telegram_id: int, status: str, member_count: int = None):
        """Update group status and metadata in database."""
        async with AsyncSessionLocal() as db:
            values = {"status": status}
            if member_count is not None:
                values["member_count"] = member_count
            
            stmt = update(Group).where(Group.telegram_id == telegram_id).values(**values)
            await db.execute(stmt)
            await db.commit()

group_analyzer = GroupQualityFilter()
