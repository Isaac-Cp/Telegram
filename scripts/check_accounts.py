from app.db.session import SessionLocal
from app.models.telegram_account import TelegramAccount
from sqlalchemy import select

with SessionLocal() as db:
    accounts = db.execute(select(TelegramAccount)).scalars().all()
    for acc in accounts:
        print(f"Phone: {acc.phone_number}, Status: {acc.status}, Joins: {acc.groups_joined}, DMs: {acc.daily_dm_count}")
