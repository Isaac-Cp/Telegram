import asyncio
import logging
from typing import Optional, List
from telethon import TelegramClient, events, functions
from telethon.sessions import StringSession
from telethon.tl.types import User
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.telegram_account import TelegramAccount
from sqlalchemy import select
from app.services.proxy_manager import proxy_manager

logger = logging.getLogger(__name__)

class TelegramClientManager:
    _instance = None
    _clients: dict[str, TelegramClient] = {} # Map phone_number to client
    _active_phone: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelegramClientManager, cls).__new__(cls)
        return cls._instance

    async def load_accounts(self) -> List[TelegramAccount]:
        """Elite Module 8: Load all active accounts."""
        with SessionLocal() as db:
            return list(db.execute(
                select(TelegramAccount).where(TelegramAccount.status == "active")
            ).scalars().all())

    async def rotate_account(self, action_type: str) -> Optional[TelegramAccount]:
        """
        Elite Module 8: Find the next available account that hasn't reached its limit.
        When account reaches limit: switch to next account.
        """
        accounts = await self.load_accounts()
        for acc in accounts:
            if self.check_account_limits(acc, action_type):
                return acc
        return None

    def check_account_limits(self, account: TelegramAccount, action_type: str) -> bool:
        """
        Elite Module 8: Each account has independent daily limits.
        """
        settings = get_settings()
        if action_type == "group_join":
            return account.groups_joined < settings.max_groups_join_per_day
        elif action_type == "dm":
            return account.daily_dm_count < settings.max_dms_per_day
        elif action_type == "public_reply":
            return account.daily_reply_count < settings.max_public_replies_per_day
        return True

    async def track_account_limits(self, phone_number: str, action_type: str):
        """
        Elite Module 8: Track and persist account limits for each action.
        """
        with SessionLocal() as db:
            acc = db.execute(
                select(TelegramAccount).where(TelegramAccount.phone_number == phone_number)
            ).scalar_one_or_none()
            
            if acc:
                if action_type == "group_join":
                    acc.groups_joined += 1
                elif action_type == "dm":
                    acc.daily_dm_count += 1
                elif action_type == "public_reply":
                    acc.daily_reply_count += 1
                
                db.commit()
                logger.info(f"Updated limits for account {phone_number} after {action_type} action.")

    async def get_client(self, phone_number: str = None, action_type: str = None) -> TelegramClient:
        """Module 8: Returns a connected Telethon client for a specific account or the next available one."""
        settings = get_settings()
        
        acc = None
        if not phone_number:
            acc = await self.rotate_account(action_type)
            if not acc:
                # Fallback to .env session if no DB accounts exist yet
                if settings.telegram_session_string:
                    return await self._connect_env_client()
                raise ValueError("No active Telegram accounts available.")
            phone_number = acc.phone_number
            session_str = acc.session_file # Using session_file as session string for now
        else:
            with SessionLocal() as db:
                acc = db.execute(
                    select(TelegramAccount).where(TelegramAccount.phone_number == phone_number)
                ).scalar_one_or_none()
                if not acc:
                    raise ValueError(f"Account {phone_number} not found.")
                session_str = acc.session_file

        if phone_number in self._clients and self._clients[phone_number].is_connected():
            return self._clients[phone_number]

        # Get proxy config (Module 2 Safety)
        proxy = proxy_manager.get_proxy_config(acc)
        if proxy and not proxy_manager.validate_proxy_connection(proxy):
            logger.warning(f"Proxy validation failed for account {phone_number}. Attempting direct connection if safe...")
            # If in production, you might want to raise an error instead of falling back
            if settings.environment == "production":
                 raise ConnectionError(f"Proxy failed for production account {phone_number}")

        api_id = acc.api_id if acc and acc.api_id else settings.telegram_api_id
        api_hash = acc.api_hash if acc and acc.api_hash else settings.telegram_api_hash

        client = TelegramClient(
            StringSession(session_str),
            api_id,
            api_hash,
            proxy=proxy
        )
        
        await client.connect()
        self._clients[phone_number] = client
        return client

    async def _connect_env_client(self) -> TelegramClient:
        """Connect using fallback .env session string."""
        settings = get_settings()
        phone = settings.telegram_phone
        
        if phone in self._clients and self._clients[phone].is_connected():
            return self._clients[phone]
            
        # Get global proxy for env client
        proxy = proxy_manager.get_proxy_config()
        
        client = TelegramClient(
            StringSession(settings.telegram_session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
            proxy=proxy
        )
        await client.connect()
        self._clients[phone] = client
        return client

    async def _on_connection_event(self, event):
        """Internal handler for logging connection events."""
        # Telethon doesn't have a simple 'on_connect' event for add_event_handler
        # but we can log state changes if we use more advanced connection listeners.
        pass

# Global instance for reusability across modules
telegram_client_manager = TelegramClientManager()

# Exportable functions as per requirements
async def connect_client():
    return await telegram_client_manager.connect_client()

async def disconnect_client():
    await telegram_client_manager.disconnect_client()

async def get_current_user():
    return await telegram_client_manager.get_current_user()
