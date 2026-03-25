import random
import asyncio
import logging
from datetime import datetime, timedelta
from telethon import functions, errors
from sqlalchemy import select, and_, func

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.group_discovery.discovery_config import DISCOVERY_LIMITS
from app.services.response_engine import response_engine
from app.services.telegram_client import telegram_client_manager

from app.models.group_join_history import GroupJoinHistory

from app.services.human_engine import human_engine

logger = logging.getLogger(__name__)

async def schedule_group_join():
    """
    Module 3: Safe Join Scheduler (Elite Upgrade)
    Join APPROVED Telegram groups safely to prevent account bans.
    """
    if not human_engine.is_within_natural_active_hours():
        return

    # 1. Fetch APPROVED quality groups (Module 2 Output)
    with SessionLocal() as db:
        target_groups = db.execute(
            select(Group).where(
                and_(
                    Group.joined == False,
                    Group.eligible_for_join == True,
                    Group.status == "APPROVED"
                )
            ).order_by(Group.authority_score.desc())
        ).scalars().all()

        if not target_groups:
            return

        for group in target_groups:
            # MODULE 28 - HUMAN BEHAVIOR ENGINE AUTHORIZATION
            if not await human_engine.authorize_action("group_join"):
                continue

            # 2. Check join history & Assign account (Module 3 Step 2 & 3)
            # Find an account that hasn't reached its join limit today (max 2 per day)
            account = await telegram_client_manager.rotate_account("group_join")
            if not account:
                logger.info("[SLIE Joiner] All accounts reached daily limit. Join scheduler: PAUSED.")
                break

            try:
                # 4. Wait random delay (5 to 30 minutes)
                await human_engine.apply_randomized_delay("group_join")

                client = await telegram_client_manager.get_client(phone_number=account.phone_number)
                
                logger.info(f"[SLIE Joiner] Account {account.phone_number} joining group: {group.name}")
                
                # Resolve target for joining
                target = group.username if group.username else group.invite_link
                if not target:
                    continue

                # 5. Join group
                await client(functions.channels.JoinChannelRequest(channel=target))
                
                # Update database & Record history
                group.joined = True
                group.status = "joined"
                
                join_record = GroupJoinHistory(
                    group_id=group.id,
                    account_id=account.id,
                    join_time=datetime.utcnow(),
                    status="success"
                )
                db.add(join_record)
                
                # Track account limit
                await telegram_client_manager.track_account_limits(account.phone_number, "group_join")
                
                db.commit()
                logger.info(f"[SLIE Joiner] joined group: {group.name}")
                
            except Exception as e:
                logger.error(f"[SLIE Joiner] Failed to join {group.name}: {e}")
                # SAFETY: mark group status = failed (Module 3 Safety)
                group.status = "failed"
                
                join_record = GroupJoinHistory(
                    group_id=group.id,
                    account_id=account.id if account else None,
                    join_time=datetime.utcnow(),
                    status="failed"
                )
                db.add(join_record)
                db.commit()

async def apply_random_join_delay():
    """
    Add randomized delays between joins (Module 4).
    join_delay = random(5–30 minutes)
    """
    delay_min = DISCOVERY_LIMITS["join_delay_min"]
    delay_max = DISCOVERY_LIMITS["join_delay_max"]
    delay = random.randint(delay_min * 60, delay_max * 60)
    
    logger.info(f"Applying safe join delay: {delay // 60} minutes...")
    await asyncio.sleep(delay)
