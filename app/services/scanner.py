import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from telethon import events, types

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.group import Group
from app.models.lead import Lead
from app.services.telegram_client import telegram_client_manager
from app.services.lead_scoring import lead_scoring_engine

logger = logging.getLogger(__name__)

PAIN_KEYWORDS = [
    "buffering", "iptv down", "channels not loading", "playlist error", 
    "xtream login failed", "server lag", "stream freezing", 
    "no signal", "m3u problem"
]

from app.services.message_scraper import message_scraper

class MessageIntelligenceScanner:
    def __init__(self):
        self.settings = get_settings()

    async def start_scanning(self):
        """Start monitoring messages in joined groups."""
        client = await telegram_client_manager.get_client()
        
        # Listen for new messages in all chats
        @client.on(events.NewMessage)
        async def message_handler(event):
            # Only process group/channel messages
            if event.is_group or event.is_channel:
                # Elite Module 1: Noise Filtering
                if not message_scraper.filter_message_noise(event):
                    return
                await self._process_incoming_message(event)

        logger.info("Message Intelligence Scanner started.")
        # Removed run_until_disconnected() as it's managed by the FastAPI app loop.

    async def _process_incoming_message(self, event):
        """Analyze message for pain signals and classify leads."""
        message_text = event.message.message
        if not message_text:
            return

        # Simple fast check for pain keywords
        has_pain_signal = any(keyword in message_text.lower() for keyword in PAIN_KEYWORDS)
        
        if not has_pain_signal:
            return

        # Get sender info
        sender = await event.get_sender()
        if not sender or isinstance(sender, (types.Channel, types.Chat)):
            return # Skip if it's from a group/channel itself

        # Check if sender is a bot
        if getattr(sender, 'bot', False):
            return

        logger.info(f"Pain signal detected in group {event.chat_id} from user {sender.id}: {message_text[:50]}...")

        # 1. Save the message first (Module 2)
        # (The message_scraper handles saving, but here we need the ID for analysis)
        # Since we are in the scanner, we can just call create_lead which now handles analysis and scoring
        
        group_id = None
        with SessionLocal() as db:
            group = db.execute(
                select(Group).where(Group.telegram_id == event.chat_id)
            ).scalar_one_or_none()
            if group:
                group_id = group.id

        # We need a message_id to link the analysis to.
        # Let's ensure the message is saved in the messages table first.
        # This is already handled by the message_scraper listener in background.
        # But we need the DB record ID.
        msg_record = None
        for _ in range(5): # Retry a few times as the scraper might be async
            with SessionLocal() as db:
                msg_record = db.execute(
                    select(Message).where(
                        Message.telegram_id == event.message.id,
                        Message.telegram_group_id == event.chat_id
                    )
                ).scalar_one_or_none()
                if msg_record:
                    break
            # Wait a bit before retrying, but don't hold the connection
            await asyncio.sleep(0.5)

        # If not found after retries, it might still be saving or failed
        # We can still create the lead without the message link if necessary,
        # but create_lead prefers it.
        await lead_scoring_engine.create_lead(
            user_id=sender.id,
            username=getattr(sender, 'username', None),
            group_id=group_id,
            message_text=message_text,
            message_id=msg_record.id if msg_record else None
        )

    # _store_lead is no longer needed as it's handled by lead_scoring_engine.create_lead
    # but I'll leave it for now if needed or delete it later.


message_intelligence_scanner = MessageIntelligenceScanner()
