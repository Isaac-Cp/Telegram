import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon import errors
from dotenv import load_dotenv

async def main():
    load_dotenv()
    
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE_NUMBER")

    if not api_id or not api_hash or not phone:
        print("ERROR: API_ID, API_HASH, and PHONE_NUMBER must be set in your .env file.")
        return

    print(f"Connecting for {phone}...")
    
    async def custom_input(prompt):
        print(f"PROMPT_REQUIRED: {prompt}")
        with open("input_required.txt", "w") as f:
            f.write(prompt)
        
        while not os.path.exists("input_response.txt"):
            await asyncio.sleep(1)
        
        with open("input_response.txt", "r") as f:
            response = f.read().strip()
        
        if os.path.exists("input_required.txt"): os.remove("input_required.txt")
        if os.path.exists("input_response.txt"): os.remove("input_response.txt")
        return response

    client = TelegramClient(
        StringSession(), 
        api_id, 
        api_hash,
        device_model="Desktop",
        system_version="Windows 10",
        app_version="4.8.4"
    )
    
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = await custom_input("Enter the code: ")
        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = await custom_input("Enter your 2FA password: ")
            await client.sign_in(password=password)
    
    session_str = client.session.save()
    print("\n" + "="*50)
    print("SESSION_GENERATED_SUCCESSFULLY")
    print(session_str)
    print("="*50 + "\n")
    
    await client.disconnect()

if __name__ == "__main__":
    for f in ["input_required.txt", "input_response.txt"]:
        if os.path.exists(f):
            os.remove(f)
    asyncio.run(main())
