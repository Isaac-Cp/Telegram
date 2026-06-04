import asyncio
from app.services.telegram_client import telegram_client_manager

async def get_me():
    client = await telegram_client_manager.get_client()
    me = await client.get_me()
    print(me.id)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(get_me())
