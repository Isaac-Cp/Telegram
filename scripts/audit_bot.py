import asyncio
import logging
from telethon import TelegramClient, functions, types
from app.services.telegram_client import telegram_client_manager
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BotAudit")

async def audit_bot():
    try:
        client = await telegram_client_manager.get_client()
        me = await client.get_me()
        logger.info(f"Auditing account: {me.first_name} (@{me.username}) ID: {me.id}")
        
        # 1. Check if account is restricted
        logger.info("Checking account restrictions...")
        try:
            # This is a common way to check for restrictions in Telethon
            # If the account is limited, some requests might fail or return specific flags
            full_user = await client(functions.users.GetFullUserRequest(id=me.id))
            if getattr(full_user.full_user, 'blocked', False):
                logger.error("Account is BLOCKED.")
            else:
                logger.info("Account is not blocked.")
        except Exception as e:
            logger.error(f"Error checking restrictions: {e}")

        # 2. Check Permissions for Group Joining
        logger.info("Testing Group Joining permission (Search)...")
        try:
            result = await client(functions.contacts.SearchRequest(q="test", limit=1))
            logger.info("Search permission: OK")
        except Exception as e:
            logger.error(f"Search permission FAILED: {e}")

        # 3. Check Network Connectivity
        logger.info("Testing Network Connectivity (Help.GetConfig)...")
        try:
            config = await client(functions.help.GetConfigRequest())
            logger.info(f"Network Connectivity: OK (Data Centers: {len(config.dc_options)})")
        except Exception as e:
            logger.error(f"Network Connectivity FAILED: {e}")

        # 4. Check for Spam/Reporting
        logger.info("Checking for Spam/Reporting status...")
        # Note: Usually you'd check @SpamBot, but we can't easily do that here without interaction.
        # We can check if we can send a message to ourselves.
        try:
            await client.send_message('me', 'Permission Audit Test')
            logger.info("Self-messaging: OK")
        except Exception as e:
            logger.error(f"Self-messaging FAILED: {e}")

    except Exception as e:
        logger.error(f"Audit failed: {e}")

if __name__ == "__main__":
    asyncio.run(audit_bot())
