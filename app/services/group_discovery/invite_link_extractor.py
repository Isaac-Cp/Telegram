import re
import logging
from datetime import datetime
from telethon import events

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.discovery_config import INVITE_LINK_PATTERNS

logger = logging.getLogger(__name__)
COMPILED_INVITE_PATTERNS = [re.compile(pattern) for pattern in INVITE_LINK_PATTERNS]

def extract_invite_links(message_text: str):
    """
    STEP 2: INVITE LINK EXTRACTION
    Extracts Telegram invite links from message text using patterns.
    """
    if not message_text:
        return []
        
    discovered_links = []
    for pattern in COMPILED_INVITE_PATTERNS:
        matches = pattern.findall(message_text)
        discovered_links.extend(matches)
        
    return list(set(discovered_links))

async def handle_message_for_invite_links(event):
    """
    Continuous extraction from monitored groups.
    If a new group link is discovered, add it to the database.
    Also handles forwarded messages (Step 2 Elite).
    """
    if not event.message:
        return
        
    text = event.message.message or ""
    
    # Handle forwarded messages which often contain original group info
    if event.message.fwd_from:
        # Check if it was forwarded from a channel/chat
        if hasattr(event.message.fwd_from, 'from_id'):
            # We can't always get the invite link from fwd_from directly, 
            # but we can look for links in the message text itself.
            pass

    invite_links = extract_invite_links(text)
    
    if not invite_links:
        return
        
    source_group_id = event.chat_id
    with SessionLocal() as db:
        for link in invite_links:
            # Clean link: ensure it's a valid t.me or joinchat URL
            clean_link = link
            if not link.startswith("http"):
                clean_link = f"https://{link}"
                
            # Check if we already have this invite link
            existing = db.query(Group).filter(Group.invite_link == clean_link).first()
            if not existing:
                # New group discovered via link (Step 10: Log Link Extracted)
                new_group = Group(
                    name=f"Link Discovered Group ({clean_link[-8:]})",
                    invite_link=clean_link,
                    discovery_source="link",
                    status="new",
                    joined=False,
                    date_discovered=datetime.utcnow()
                )
                db.add(new_group)
                logger.info(f"SLIE Discovery: Invite link extracted: {clean_link} (Source Group: {source_group_id})")
        
        db.commit()
