import asyncio
import logging
from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.join_scheduler import schedule_group_join

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForceJoin")

async def force_join():
    with SessionLocal() as db:
        # 1. Find 5 groups that were discovered but rejected
        groups = db.execute(
            select(Group).where(Group.joined == False).order_by(Group.members_count.desc()).limit(5)
        ).scalars().all()
        
        if not groups:
            logger.error("No groups found in database to force approve.")
            return

        for group in groups:
            logger.info(f"Force approving group: {group.name} ({group.members_count} members)")
            group.status = "APPROVED"
            group.eligible_for_join = True
            group.authority_score = 100
        
        # 2. Reset account limits for demonstration
        from app.models.telegram_account import TelegramAccount
        accounts = db.execute(select(TelegramAccount)).scalars().all()
        for acc in accounts:
            logger.info(f"Resetting limits for account: {acc.phone_number}")
            acc.groups_joined = 0
            acc.daily_dm_count = 0
            acc.daily_reply_count = 0
        
        db.commit()

    # 2. Run the joiner
    logger.info("Running joiner for 5 groups...")
    for i in range(5):
        await schedule_group_join()
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(force_join())
