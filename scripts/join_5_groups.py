import asyncio
import logging
from sqlalchemy import select, and_, func
from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.discovery_engine import discovery_engine
from app.services.group_discovery.join_scheduler import schedule_group_join
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JoinScript")

async def run_join_flow():
    settings = get_settings()
    
    with SessionLocal() as db:
        # 1. Check for approved groups
        approved_count = db.execute(
            select(func.count(Group.id)).where(
                and_(
                    Group.joined == False,
                    Group.eligible_for_join == True,
                    Group.status == "APPROVED"
                )
            )
        ).scalar() or 0
        
        logger.info(f"Currently have {approved_count} approved groups ready to join.")
        
        if approved_count < 5:
            logger.info("Not enough approved groups. Running discovery and analysis...")
            # Trigger discovery
            await discovery_engine.run_keyword_search_task()
            # Trigger analysis (this will approve/reject based on the new Buyer Density logic)
            await discovery_engine.run_group_analysis_task()
            
            # Re-check count
            approved_count = db.execute(
                select(func.count(Group.id)).where(
                    and_(
                        Group.joined == False,
                        Group.eligible_for_join == True,
                        Group.status == "APPROVED"
                    )
                )
            ).scalar() or 0
            logger.info(f"After discovery/analysis, have {approved_count} approved groups.")

    if approved_count > 0:
        logger.info("Executing join scheduler...")
        # Note: schedule_group_join has built-in rate limits and randomization
        # We might need to call it multiple times or adjust it for this one-off run
        for i in range(5):
            await schedule_group_join()
            # Wait a bit between iterations to allow the scheduler to process next group
            await asyncio.sleep(2)
    else:
        logger.warning("No approved groups found even after discovery. Check logs for AI analysis results.")

if __name__ == "__main__":
    asyncio.run(run_join_flow())
