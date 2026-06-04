import asyncio
import logging
print("DEBUG: Script started")
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.group import Group
from app.models.lead import Lead
from app.services.telegram_client import telegram_client_manager
from app.services.group_discovery.keyword_search import search_groups_by_keyword
from app.services.group_discovery.group_analyzer import collect_group_metadata, analyze_group_activity
from app.services.group_discovery.authority_scoring import calculate_authority_score
from app.services.group_discovery.join_scheduler import schedule_group_join
from app.services.response_engine import response_engine
from app.services.message_scraper import start_message_listener

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_session.log", encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger("BotSession")

async def run_session(duration_minutes=50, target_dms=1):
    """
    Runs the bot session for a specific duration.
    """
    start_time_dt = datetime.now(timezone.utc)
    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    dms_sent = 0
    joins_done = 0
    
    logger.info(f"Starting bot session for {duration_minutes} minutes. Target DMs: {target_dms}")
    
    # 1. Initialize client
    try:
        client = await telegram_client_manager.get_client()
        me = await client.get_me()
        logger.info(f"Bot session active as: {me.username}")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        return

    # 2. Start message listener in background to capture leads
    logger.info("Starting background message listener...")
    asyncio.create_task(start_message_listener(client))

    while datetime.now() < end_time:
        remaining = (end_time - datetime.now()).total_seconds() / 60
        logger.info(f"Session progress: {remaining:.1f} minutes remaining. DMs sent: {dms_sent}/{target_dms}")
        
        # A. Find groups if we need more
        keywords = ["global chat", "public group", "telegram community", "gaming chat", "crypto talk"]
        for keyword in keywords:
            logger.info(f"Searching for groups: {keyword}")
            await search_groups_by_keyword(client, keyword)
        
        # B. Analyze and Approve groups
        with SessionLocal() as db:
            new_groups = db.execute(
                select(Group).where(Group.status == "new").limit(5)
            ).scalars().all()
            
            for group in new_groups:
                logger.info(f"Analyzing: {group.name}")
                if await collect_group_metadata(client, group):
                    if await analyze_group_activity(client, group):
                        calculate_authority_score(group)
                        group.status = "APPROVED"
                        group.eligible_for_join = True
                        db.commit()
                        logger.info(f"Group APPROVED: {group.name}")
        
        # C. Join groups
        if joins_done < 1:
            logger.info("Running join scheduler...")
            await schedule_group_join()
            
            # Verify if a group was joined
            with SessionLocal() as db:
                joined_count = db.query(Group).filter(
                    Group.joined == True,
                    Group.updated_at >= start_time_dt
                ).count()
                if joined_count > joins_done:
                    joins_done = joined_count
                    logger.info(f"Progress: {joins_done} groups joined.")
        
        # D. Check for leads and send DMs
        if dms_sent < target_dms:
            logger.info("Checking for qualified leads to DM...")
            # Use process_private_dms which handles prioritization and safety
            await response_engine.process_private_dms()
            
            # Count DMs sent in this session
            with SessionLocal() as db:
                new_dms = db.query(Lead).filter(
                    Lead.dm_sent == True,
                    Lead.last_contact >= start_time_dt
                ).count()
                
                if new_dms > dms_sent:
                    dms_sent = new_dms
                    logger.info(f"Progress: {dms_sent} DMs confirmed sent.")
        
        if dms_sent >= target_dms and joins_done >= 1:
            logger.info("Session goals reached (1 DM, 1 Join)! Continuing to monitor for remaining time...")
        
        # Sleep between cycles to avoid flood limits
        await asyncio.sleep(300) # 5 minute cycle

    logger.info("Bot session completed successfully.")

if __name__ == "__main__":
    print("DEBUG: Calling asyncio.run(run_session())")
    try:
        asyncio.run(run_session())
    except KeyboardInterrupt:
        logger.info("Session interrupted by user.")
    except Exception as e:
        logger.error(f"Session failed with error: {e}")
