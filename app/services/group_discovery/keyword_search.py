import logging
from typing import List
from telethon import functions
from telethon.tl.types import Channel, Chat

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.discovery_config import TARGET_KEYWORDS

logger = logging.getLogger(__name__)

async def search_groups_by_keyword(client, keyword: str):
    """
    STEP 1: KEYWORD SEARCH ENGINE
    Searches Telegram for groups using keywords and stores discovered groups in the database.
    """
    logger.info(f"Searching Telegram groups for keyword: {keyword}")
    try:
        # Search for public channels/groups
        result = await client(functions.contacts.SearchRequest(
            q=keyword,
            limit=50
        ))
        
        discovered_count = 0
        with SessionLocal() as db:
            # result.chats contains the discovered channels/groups
            for chat in result.chats:
                if not isinstance(chat, (Channel, Chat)):
                    continue
                    
                # Basic metadata extraction
                group_id = chat.id
                group_name = chat.title
                username = getattr(chat, 'username', None)
                
                # Check if we already have this group
                existing = db.query(Group).filter(Group.telegram_id == group_id).first()
                if not existing:
                    # New group discovered (Step 10: Log Group Discovered)
                    new_group = Group(
                        telegram_id=group_id,
                        name=group_name,
                        username=username,
                        discovery_source="search",
                        status="new",
                        joined=False
                    )
                    db.add(new_group)
                    discovered_count += 1
                    logger.info(f"SLIE Discovery: Group discovered via search: {group_name} (@{username or 'no_user'})")
            
            db.commit()
            logger.info(f"Keyword '{keyword}' search completed. Discovered {discovered_count} new groups.")
            
    except Exception as e:
        logger.error(f"Error searching groups by keyword '{keyword}': {e}")

async def run_keyword_discovery(client):
    """Orchestrates keyword search across all target keywords."""
    for keyword in TARGET_KEYWORDS:
        await search_groups_by_keyword(client, keyword)
