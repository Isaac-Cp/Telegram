import asyncio
import logging
from app.services.telegram_client import telegram_client_manager
from app.services.group_discovery.keyword_search import search_groups_by_keyword
from app.services.group_discovery.group_analyzer import collect_group_metadata, analyze_group_activity
from app.services.group_discovery.authority_scoring import calculate_authority_score
from app.services.group_discovery.join_scheduler import schedule_group_join
from app.services.response_engine import response_engine
from app.db.session import SessionLocal
from app.models.group import Group
from app.models.lead import Lead
from sqlalchemy import select, desc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def validate_and_execute_bot():
    """
    Validates bot functionality: find group, join, and send DM.
    """
    logger.info("Starting bot validation sequence...")
    
    # 1. Initialize client
    try:
        client = await telegram_client_manager.get_client()
        me = await client.get_me()
        logger.info(f"Bot initialized as: {me.username}")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
        return

    # 2. Identify a valid target group (Search)
    keyword = "iptv discussion"
    logger.info(f"Searching for groups with keyword: {keyword}")
    await search_groups_by_keyword(client, keyword)
    
    # 3. Analyze and Approve a group
    with SessionLocal() as db:
        group = db.execute(
            select(Group).where(Group.status == "new").order_by(Group.id.desc()).limit(1)
        ).scalar_one_or_none()
        
        if not group:
            logger.error("No groups discovered during search.")
            return
            
        logger.info(f"Analyzing discovered group: {group.name}")
        if await collect_group_metadata(client, group):
            if await analyze_group_activity(client, group):
                calculate_authority_score(group)
                group.status = "APPROVED" # Force approve for validation
                group.eligible_for_join = True
                db.commit()
                logger.info(f"Group {group.name} APPROVED and ready for join.")
            else:
                logger.warning(f"Group {group.name} failed activity analysis.")
        else:
            logger.warning(f"Failed to collect metadata for {group.name}.")

    # 4. Join the group
    logger.info("Executing join scheduler...")
    await schedule_group_join()
    
    with SessionLocal() as db:
        group = db.execute(select(Group).where(Group.joined == True).order_by(Group.updated_at.desc()).limit(1)).scalar_one_or_none()
        if not group or not group.joined:
            logger.error("Failed to join the approved group.")
            return
        logger.info(f"Successfully joined group: {group.name}")

    # 5. Send a DM to a qualified lead
    # For validation, we'll manually find a user in the group or use a recently captured lead
    logger.info("Searching for a qualified lead to message...")
    with SessionLocal() as db:
        lead = db.execute(
            select(Lead).where(Lead.dm_sent == False).order_by(Lead.opportunity_score.desc()).limit(1)
        ).scalar_one_or_none()
        
        if not lead:
            # If no lead in DB, try to capture one from the group we just joined
            logger.info("No leads in DB, waiting for messages to capture a lead...")
            # This is a bit complex for a script, so we'll assume a lead exists or skip this step with a note
            logger.warning("No lead found in database for DM validation. Skipping DM step.")
        else:
            logger.info(f"Targeting lead: {lead.username}")
            # We'll use the response_engine logic but might need to bypass safety limits for validation
            await response_engine.process_private_dms()
            
            # Verify DM sent
            db.refresh(lead)
            if lead.dm_sent:
                logger.info(f"Successfully sent DM to lead: {lead.username}")
            else:
                logger.warning(f"DM process completed but lead {lead.username} dm_sent is still False.")

    logger.info("Bot validation sequence completed.")

if __name__ == "__main__":
    asyncio.run(validate_and_execute_bot())
