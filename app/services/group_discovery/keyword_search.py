import logging

from telethon import functions
from telethon.tl.types import Channel

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.discovery_config import TARGET_KEYWORDS

logger = logging.getLogger(__name__)


async def search_groups_by_keyword(client, keyword: str):
    """
    Search Telegram for public megagroups/forums and store only viable
    candidate communities.
    """
    logger.info("Searching Telegram groups for keyword: %s", keyword)
    try:
        result = await client(functions.contacts.SearchRequest(q=keyword, limit=50))

        discovered_count = 0
        with SessionLocal() as db:
            for chat in result.chats:
                if not isinstance(chat, Channel):
                    continue

                username = getattr(chat, "username", None)
                if not username:
                    continue

                if getattr(chat, "broadcast", False):
                    continue

                if not (getattr(chat, "megagroup", False) or getattr(chat, "forum", False)):
                    continue

                if any(getattr(chat, attr, False) for attr in ("scam", "fake", "restricted")):
                    continue

                existing = db.query(Group).filter(Group.telegram_id == chat.id).first()
                if existing:
                    continue

                db.add(
                    Group(
                        telegram_id=chat.id,
                        name=chat.title,
                        username=username,
                        members_count=getattr(chat, "participants_count", 0) or 0,
                        discovery_source="search",
                        status="new",
                        joined=False,
                    )
                )
                discovered_count += 1
                logger.info("SLIE Discovery: Group discovered via search: %s (@%s)", chat.title, username)

            db.commit()
            logger.info("Keyword '%s' search completed. Discovered %s new groups.", keyword, discovered_count)

    except Exception as exc:
        logger.error("Error searching groups by keyword '%s': %s", keyword, exc)


async def run_keyword_discovery(client):
    """Orchestrates keyword search across all target keywords."""
    for keyword in TARGET_KEYWORDS:
        await search_groups_by_keyword(client, keyword)
