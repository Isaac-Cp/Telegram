import asyncio
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.telegram_account import TelegramAccount

async def check_accounts():
    with SessionLocal() as db:
        accounts = db.execute(select(TelegramAccount)).scalars().all()
        print(f"Total accounts in DB: {len(accounts)}")
        for acc in accounts:
            print(f"Phone: {acc.phone_number}, Status: {acc.status}, Joins Today: {acc.groups_joined}")

if __name__ == "__main__":
    asyncio.run(check_accounts())
