import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
from dotenv import load_dotenv

async def main():
    load_dotenv()
    
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE_NUMBER")

    if not api_id or not api_hash or not phone:
        print("Error: API_ID, API_HASH, and PHONE_NUMBER must be set in your .env file.")
        return

    print(f"Connecting for {phone}...")
    
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_str = client.session.save()
        print("\n" + "="*50)
        print("YOUR SESSION STRING (Copy this to SESSION_STRING in .env):")
        print("="*50)
        print(session_str)
        print("="*50 + "\n")
        print("Keep this string safe! It grants full access to your Telegram account.")

if __name__ == "__main__":
    asyncio.run(main())
