import logging
import asyncio
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, and_, func

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.keyword_search import run_keyword_discovery
from app.services.group_discovery.group_analyzer import collect_group_metadata, analyze_group_activity
from app.services.group_discovery.authority_scoring import calculate_authority_score
from app.services.group_discovery.join_scheduler import schedule_group_join
from app.services.telegram_client import telegram_client_manager

logger = logging.getLogger(__name__)

class GroupDiscoveryEngine:
    """
    STEP 8: GROUP APPROVAL PIPELINE
    STEP 9: AUTOMATION LOOP
    The discovery engine runs periodically to find, evaluate, rank, and safely join groups.
    """
    def __init__(self):
        self.is_running = False

    async def run_keyword_search_task(self):
        """Keyword search task (Runs every 6 hours)."""
        logger.info("Starting SLIE Group Discovery Engine: Keyword Search...")
        client = await telegram_client_manager.get_client()
        await run_keyword_discovery(client)
        logger.info("Keyword search task completed.")

    async def run_external_discovery_task(self):
        """Step 2.5: Discover groups from external sources like Reddit (Every 12h)."""
        logger.info("Starting SLIE Group Discovery Engine: External Sources (Reddit)...")
        from app.models.external_lead import ExternalLead
        from app.services.group_discovery.invite_link_extractor import extract_invite_links

        with SessionLocal() as db:
            # Find reddit leads with invite links in content
            external_leads = db.execute(
                select(ExternalLead).where(
                    (ExternalLead.source == "reddit") & 
                    (ExternalLead.content.contains("t.me/"))
                )
            ).scalars().all()

            for lead in external_leads:
                links = extract_invite_links(lead.content)
                for link in links:
                    clean_link = link if link.startswith("http") else f"https://{link}"
                    
                    existing = db.query(Group).filter(
                        (Group.invite_link == clean_link) | (Group.username == link.split('/')[-1])
                    ).first()
                    
                    if not existing:
                        new_group = Group(
                            name=f"Reddit Discovered Group ({clean_link[-8:]})",
                            invite_link=clean_link,
                            discovery_source="reddit",
                            status="new",
                            joined=False
                        )
                        db.add(new_group)
                        logger.info(f"New group discovered via Reddit link: {clean_link}")
            db.commit()

    async def run_group_analysis_task(self):
        """Group metadata collection and activity analysis (Runs every 12 hours)."""
        logger.info("Starting SLIE Group Discovery Engine: Group Analysis...")
        client = await telegram_client_manager.get_client()
        
        with SessionLocal() as db:
            # Find groups that are new or haven't been scanned in 12 hours
            twelve_hours_ago = datetime.utcnow() - timedelta(hours=12)
            target_groups = db.execute(
                select(Group).where(
                    and_(
                        Group.joined == False,
                        (Group.status == "new") | (Group.last_scanned <= twelve_hours_ago)
                    )
                )
            ).scalars().all()

            for group in target_groups:
                # 1. Collect metadata
                if not await collect_group_metadata(client, group):
                    db.commit()
                    continue
                    
                # 2. Analyze activity
                if not await analyze_group_activity(client, group):
                    db.commit()
                    continue
                    
                # 3. Calculate authority score (Step 5)
                calculate_authority_score(group)
                
                db.commit()
                logger.info(f"Group {group.name} analyzed. Status: {group.status}, Authority Score: {group.authority_score}")
                
        logger.info("Group analysis task completed.")

    async def run_join_scheduler_task(self):
        """Join scheduler task (Runs every hour)."""
        logger.info("Starting SLIE Group Discovery Engine: Join Scheduler...")
        await schedule_group_join()
        logger.info("Join scheduler task completed.")

# Instantiate the discovery engine service
discovery_engine = GroupDiscoveryEngine()
