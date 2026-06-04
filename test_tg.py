import asyncio
import logging
from app.services.telegram_client import telegram_client_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

async def test_conn():
    try:
        client = await telegram_client_manager.get_client()
        me = await client.get_me()
        logger.info(f"Connected as: {me.username}")
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_conn())
