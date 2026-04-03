import logging
import re
from typing import List, Set
from telethon import functions, types
from slie.telegram.telegram_client import telegram_engine
from slie.core.database import AsyncSessionLocal
from slie.models.group_models import Group
from sqlalchemy import select

logger = logging.getLogger(__name__)

class GroupDiscoveryEngine:
    """
    STEP 4: GROUP DISCOVERY ENGINE
    Purpose: Find new communities related to IPTV.
    """
    KEYWORDS = [
        "iptv", "iptv help", "iptv discussion", 
        "streaming help", "smart tv channels",
        "xtream codes", "m3u list", "iptv reviews"
    ]

    async def discover_groups(self):
        """Search Telegram for groups matching keywords."""
        if not telegram_engine.client:
            logger.error("[SLIE Discovery] Telegram client not connected.")
            return

        all_discovered_links = set()

        for keyword in self.KEYWORDS:
            logger.info(f"[SLIE Discovery] Searching for groups with keyword: {keyword}")
            try:
                result = await telegram_engine.client(functions.contacts.SearchRequest(
                    q=keyword,
                    limit=50
                ))
                
                for chat in result.chats:
                    if isinstance(chat, (types.Chat, types.Channel)):
                        if hasattr(chat, 'username') and chat.username:
                            link = f"https://t.me/{chat.username}"
                            all_discovered_links.add(link)
                            await self._store_discovered_group(chat)

            except Exception as e:
                logger.error(f"[SLIE Discovery] Error searching for {keyword}: {str(e)}")

        logger.info(f"[SLIE Discovery] Total unique groups discovered: {len(all_discovered_links)}")
        return list(all_discovered_links)

    async def _store_discovered_group(self, chat):
        """Store discovered group in the database if it doesn't exist."""
        async with AsyncSessionLocal() as db:
            # Check if group already exists
            stmt = select(Group).where(Group.telegram_id == chat.id)
            existing = await db.execute(stmt)
            if existing.scalar_one_or_none():
                return

            new_group = Group(
                telegram_id=chat.id,
                name=chat.title,
                username=getattr(chat, 'username', None),
                member_count=getattr(chat, 'participants_count', 0),
                status="DISCOVERED"
            )
            db.add(new_group)
            await db.commit()
            logger.info(f"[SLIE Discovery] Group discovered: {chat.title} ({chat.id})")

discovery_engine = GroupDiscoveryEngine()
