import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

load_dotenv()

async def test_session():
    import requests
    try:
        ip = requests.get('https://api.ipify.org').text
        print(f"Current IP: {ip}")
    except:
        print("Could not get IP")
    
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_str = os.getenv("SESSION_STRING")
    
    print(f"Testing session with API_ID: {api_id}")
    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    try:
        await client.connect()
        me = await client.get_me()
        print(f"Successfully connected as: {me.username}")
        await client.disconnect()
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_session())
