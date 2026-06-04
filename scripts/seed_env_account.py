from app.db.session import SessionLocal
from app.models.telegram_account import TelegramAccount
from app.core.config import get_settings
from sqlalchemy import select

settings = get_settings()

with SessionLocal() as db:
    # Check if the env account already exists
    existing = db.execute(
        select(TelegramAccount).where(TelegramAccount.phone_number == settings.telegram_phone)
    ).scalar_one_or_none()
    
    if not existing:
        new_acc = TelegramAccount(
            phone_number=settings.telegram_phone,
            session_file=settings.telegram_session_string,
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            status="active",
            groups_joined=0,
            daily_dm_count=0,
            daily_reply_count=0
        )
        db.add(new_acc)
        db.commit()
        print(f"Added account {settings.telegram_phone} to database.")
    else:
        print(f"Account {settings.telegram_phone} already exists.")
