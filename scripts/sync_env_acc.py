import asyncio
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.telegram_account import TelegramAccount
from sqlalchemy import select

async def sync_env_to_db():
    settings = get_settings()
    if not settings.telegram_session_string:
        print("No TELEGRAM_SESSION_STRING in .env")
        return

    with SessionLocal() as db:
        # Check if already exists
        existing = db.execute(
            select(TelegramAccount).where(TelegramAccount.phone_number == "Primary")
        ).scalar_one_or_none()
        
        if not existing:
            print("Adding Primary account from .env to DB...")
            acc = TelegramAccount(
                phone_number="Primary",
                session_file=settings.telegram_session_string,
                status="active",
                groups_joined=0
            )
            db.add(acc)
            db.commit()
            print("Account added successfully.")
        else:
            print("Primary account already exists in DB.")

if __name__ == "__main__":
    asyncio.run(sync_env_to_db())
