import asyncio
import logging
from typing import Optional, List
from telethon import TelegramClient, functions, errors
from telethon.sessions import StringSession
from slie.core.config import get_settings
from slie.core.database import AsyncSessionLocal
from slie.models.lead_models import User as DBUser
from sqlalchemy import select

logger = logging.getLogger(__name__)

class TelegramClientEngine:
    """
    STEP 3: TELEGRAM CLIENT ENGINE
    Implement Telethon client with robust error handling.
    """
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[TelegramClient] = None
        self.is_running = False

    async def connect(self, session_str: str = None) -> TelegramClient:
        """
        Connect using api_id and api_hash.
        Load session file/string.
        """
        try:
            session = StringSession(session_str) if session_str else StringSession(self.settings.telegram_session_string)
            self.client = TelegramClient(
                session,
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash,
                device_model="SLIE Intelligence Node",
                system_version="4.16.30-vx-custom"
            )
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.warning("[SLIE Telegram] Client not authorized. Manual intervention required.")
                return None
            
            self.is_running = True
            logger.info(f"[SLIE Telegram] Client connected and authorized. (Version: {self.settings.version})")
            return self.client

        except errors.FloodWaitError as e:
            logger.error(f"[SLIE Telegram] FloodWait: Must wait {e.seconds} seconds.")
            await asyncio.sleep(e.seconds)
            return await self.connect(session_str)
        except Exception as e:
            logger.error(f"[SLIE Telegram] Connection failure: {str(e)}")
            return None

    async def join_group(self, invite_link: str) -> bool:
        """Join groups with safety handling."""
        if not self.client:
            return False
        try:
            await self.client(functions.messages.ImportChatInviteRequest(hash=invite_link.split('/')[-1]))
            logger.info(f"[SLIE Telegram] Successfully joined group via {invite_link}")
            return True
        except errors.FloodWaitError as e:
            logger.warning(f"[SLIE Safety] Cooldown activated: FloodWait for {e.seconds}s during join.")
            return False
        except Exception as e:
            logger.error(f"[SLIE Telegram] Failed to join group: {str(e)}")
            return False

    async def send_reply(self, chat_id: int, message_id: int, text: str) -> bool:
        """Send replies to specific messages."""
        if not self.client:
            return False
        try:
            await self.client.send_message(chat_id, text, reply_to=message_id)
            logger.info(f"[SLIE Engagement] Public reply sent to {chat_id}")
            return True
        except errors.FloodWaitError as e:
            logger.warning(f"[SLIE Safety] Cooldown activated: FloodWait for {e.seconds}s during reply.")
            return False
        except Exception as e:
            logger.error(f"[SLIE Telegram] Failed to send reply: {str(e)}")
            return False

    async def send_private_message(self, user_id: int, text: str) -> bool:
        """Send private messages to leads."""
        if not self.client:
            return False
        try:
            await self.client.send_message(user_id, text)
            logger.info(f"[SLIE Engagement] DM sent to user {user_id}")
            return True
        except errors.FloodWaitError as e:
            logger.warning(f"[SLIE Safety] Cooldown activated: FloodWait for {e.seconds}s during DM.")
            return False
        except Exception as e:
            logger.error(f"[SLIE Telegram] Failed to send DM: {str(e)}")
            return False

    def add_event_handler(self, callback, event_type):
        """Add event handler to the client."""
        if self.client:
            self.client.add_event_handler(callback, event_type)
            logger.info(f"[SLIE Telegram] Registered event handler: {callback.__name__}")

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
            self.is_running = False
            logger.info("[SLIE Telegram] Client disconnected.")

telegram_engine = TelegramClientEngine()
