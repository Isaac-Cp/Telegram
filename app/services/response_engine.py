import asyncio
import logging
import random
from datetime import datetime, timedelta, time as dt_time
from typing import List

from sqlalchemy import select, and_, func, case
from sqlalchemy.orm import Session
from telethon import functions, types

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.lead_conversation import LeadConversation
from app.models.group import Group
from app.models.enums import ConversionStage
from app.services.telegram_client import telegram_client_manager
from app.services.lead_scoring import lead_scoring_engine
from app.services.crm import lead_crm_service
from app.services.ai_service import ai_service
from app.services.power_upgrades import power_upgrades_service
from app.services.memory_engine import memory_engine
from app.services.ltv_engine import ltv_engine
from app.services.human_engine import human_engine

logger = logging.getLogger(__name__)

AIDEN_SYSTEM_PROMPT = """
You are Aiden, Senior Technical Architect for Streamexpert. 
 
Your role is to assist IPTV users with technical explanations and guide them toward reseller panels or premium subscriptions. 
 
COMMON USER QUESTIONS:
- Price / Cost
- Free Trial availability
- Reseller panel setup
- Technical setup instructions
- Device compatibility (Smart TV, Firestick, etc.)

RESPONSE RULES: 
- Professional, technical tone.
- Provide detailed technical explanations first.
- Never use aggressive selling.
- Provide helpful insights before any CTA.
- 50-80 words, 4-5 sentences.
- max 2 emojis 🤝 📺 💎 
"""

class ResponseEngine:
    def __init__(self):
        self.settings = get_settings()

    async def check_daily_limits(self, db: Session, action_type: str) -> bool:
        """
        Elite Module 4: Human Behavior Engine - Action Limits.
        groups joined per day = 2
        public replies per day = 5
        direct messages per day = 10
        """
        from datetime import date
        today = date.today()
        
        if action_type == "group_join":
            count = db.query(func.count(Group.id)).filter(
                Group.joined == True,
                func.date(Group.updated_at) == today
            ).scalar() or 0
            return count < 2
            
        elif action_type == "public_reply":
            count = db.query(func.count(Lead.id)).filter(
                Lead.public_reply_sent == True,
                func.date(Lead.updated_at) == today
            ).scalar() or 0
            return count < 5
            
        elif action_type == "dm":
            count = db.query(func.count(Lead.id)).filter(
                Lead.dm_sent == True,
                func.date(Lead.last_contact) == today
            ).scalar() or 0
            return count < 10
            
        return True

    async def simulate_typing(self, client, chat_id, delay_range=(3, 10)):
        """
        Elite Module 4: Human Behavior Engine - Typing Delay.
        Typing delay: 3–10 seconds before sending messages.
        """
        if not self.is_within_active_hours():
            return
            
        delay = random.randint(*delay_range)
        logger.info(f"Simulating typing for {delay} seconds in {chat_id}...")
        try:
            async with client.action(chat_id, 'typing'):
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"Error simulating typing: {e}")
            await asyncio.sleep(delay)

    def is_within_active_hours(self) -> bool:
        """
        Elite Module 4: Human Behavior Engine - Random Activity Windows.
        Fully Autonomous Mode: Follows BUSINESS_HOURS from .env or allows 24/7.
        """
        try:
            start_h = int(getattr(self.settings, "business_hours_start", 0))
            end_h = int(getattr(self.settings, "business_hours_end", 23))
        except:
            start_h, end_h = 0, 23

        # If 0-23, it's 24/7
        if start_h == 0 and end_h == 23:
            return True

        now = datetime.now().time()
        # Handle overnight hours (e.g., 22:00 to 06:00)
        if start_h <= end_h:
            is_active = (dt_time(hour=start_h, minute=0) <= now <= dt_time(hour=end_h, minute=59, second=59))
        else:
            is_active = (now >= dt_time(hour=start_h, minute=0) or now <= dt_time(hour=end_h, minute=59, second=59))
        
        if not is_active:
            logger.info(f"Current time {now} is outside configured active hours ({start_h}:00-{end_h}:00). Human Behavior Engine: SLEEP.")
        return is_active

    async def apply_random_delay(self, action_type: str):
        """
        Elite Module 4: Human Behavior Engine - Random Delays.
        group join delay = 5–30 minutes
        public reply delay = 20 minutes
        dm delay = 15–45 minutes
        """
        delays = {
            "group_join": (5 * 60, 30 * 60),
            "public_reply": (20 * 60, 20 * 60), # Exact 20 minutes
            "dm": (15 * 60, 45 * 60)
        }
        
        range_val = delays.get(action_type, (5 * 60, 15 * 60))
        delay = random.randint(*range_val)
        logger.info(f"Applying {action_type} delay: {delay // 60} minutes...")
        await asyncio.sleep(delay)

    async def manage_active_hours(self):
        """
        Main simulation loop that manages active windows and online status (Module 3).
        Occasionally appear online without sending messages.
        """
        client = await telegram_client_manager.get_client()
        while True:
            try:
                if self.is_within_active_hours():
                    # Randomly "appear online"
                    if random.random() < 0.3: # 30% chance every check
                        logger.info("Simulation: Appearing online...")
                        await client(functions.account.UpdateStatusRequest(offline=False))
                else:
                    # Sleep outside active hours
                    await client(functions.account.UpdateStatusRequest(offline=True))
                    
                # Check every 15-30 minutes
                await asyncio.sleep(random.randint(15 * 60, 30 * 60))
            except Exception as e:
                logger.error(f"Error in manage_active_hours loop: {e}")
                await asyncio.sleep(600)

    async def generate_public_response(self, lead_id: str, message_text: str, persona: dict) -> str:
        """
        Elite Module 15: Generate a public technical response with conversation context.
        """
        context = memory_engine.get_ai_context(lead_id)
        
        system_prompt = f"""
        You are {persona['name']}, {persona['role']} for Streamexpert.
        Expertise: {persona['expertise']}
        Tone: {persona['tone']}
        
        Provide a helpful, authoritative technical explanation.
        {context}
        
        RULES: 
        - be helpful
        - 40-60 words
        - max 1 emoji
        """
        
        prompt = f"Lead Message: {message_text}\n\nProvide a technical authority response."
        
        try:
            content = await ai_service.chat_completion(
                prompt=prompt,
                system_prompt=system_prompt
            )
            return content if content else "Streaming node congestion often results in visible buffering during peak sports events. This typically occurs when providers over-provision their existing server bandwidth. High-concurrency infrastructure designed with dedicated edge nodes usually mitigates this issue entirely."
        except Exception as e:
            logger.error(f"Error generating public response: {e}")
            return "Streaming node congestion often results in visible buffering during peak sports events. This typically occurs when providers over-provision their existing server bandwidth. High-concurrency infrastructure designed with dedicated edge nodes usually mitigates this issue entirely."

    async def generate_dm_response(self, lead_id: str, message_text: str, persona: dict) -> str:
        """
        Elite Module 15: Generate a private DM based on LTV and Memory.
        """
        context = memory_engine.get_ai_context(lead_id)
        
        system_prompt = f"""
        You are {persona['name']}, {persona['role']} for Streamexpert.
        Expertise: {persona['expertise']}
        Tone: {persona['tone']}
        
        Provide a personalized private DM follow-up.
        {context}
        
        RULES: 
        - personal tone
        - 30-50 words
        - max 1 emoji
        """
        
        prompt = f"Lead Message: {message_text}\n\nProvide a private follow-up response."
        
        try:
            content = await ai_service.chat_completion(
                prompt=prompt,
                system_prompt=system_prompt
            )
            return content if content else "Hope your buffering issues cleared up. If not, our reseller panels offer more direct server routes which usually resolve that."
        except Exception as e:
            logger.error(f"Error generating DM response: {e}")
            return "Hope your buffering issues cleared up. If not, our reseller panels offer more direct server routes which usually resolve that."

    async def generate_private_dm(self, lead: Lead) -> str:
        """
        Elite Module 15 & 16: Generate a personalized DM based on LTV and Memory.
        """
        persona = power_upgrades_service.select_persona(lead)
        context = memory_engine.get_ai_context(lead.id)
        
        # Check if high value reseller prospect (Module 16)
        is_reseller = "reseller" in (lead.ltv_score_record.ltv_level if lead.ltv_score_record else "")
        
        strategy = ""
        if is_reseller:
            strategy = "STRATEGY: Mention reseller panels, credit systems, and wholesale infrastructure."
        
        system_prompt = f"""
        You are {persona['name']}, {persona['role']} for Streamexpert.
        Expertise: {persona['expertise']}
        Tone: {persona['tone']}
        
        {strategy}
        
        Generate a personalized DM follow-up.
        {context}
        
        RULES: 
        - be helpful
        - 50-80 words
        - end with a question
        """
        
        prompt = f"Lead Original Message: {lead.original_message}\n\nProvide a technical authority follow-up DM."
        
        try:
            content = await ai_service.chat_completion(
                prompt=prompt,
                system_prompt=system_prompt
            )
            return content if content else f"I noticed your technical issue earlier. As a {persona['role']}, I can tell you most providers fail at scale because they lack proper concurrency management. Streamexpert uses a distributed architecture to avoid exactly this. Would you like to see a demo? 🤝"
        except Exception as e:
            logger.error(f"Error generating private DM: {e}")
            return "I noticed your technical issue earlier. Most providers fail at scale because they lack proper concurrency management. Streamexpert uses a distributed architecture to avoid exactly this. Would you like to see a demo? 🤝"

    async def process_public_replies(self):
        """
        Elite Module 4 & 8: Process and send public replies to leads.
        Uses Human Behavior Engine for authorization and randomization.
        """
        if not human_engine.is_within_natural_active_hours():
            return

        # Authorization check (Daily Limits)
        if not await human_engine.authorize_action("public_reply"):
            return

        # Find an account that can perform a public reply (Module 8)
        account = await telegram_client_manager.rotate_account("public_reply")
        
        if account:
            client = await telegram_client_manager.get_client(phone_number=account.phone_number)
            phone_number = account.phone_number
        else:
            # Fallback to .env account if session string exists
            if self.settings.telegram_session_string:
                client = await telegram_client_manager.get_client()
                phone_number = self.settings.telegram_phone
            else:
                logger.info("No active Telegram accounts with remaining public reply limits.")
                return
        
        with SessionLocal() as db:
            # Elite Module 14: Prioritize leads based on Priority Tiers
            # Fully Autonomous Mode: Include HIGH and MEDIUM leads (User Request)
            lead_ids = db.execute(
                select(Lead.id).where(
                    and_(
                        Lead.priority_level.in_(["HIGH", "MEDIUM"]),
                        Lead.public_reply_sent == False,
                        Lead.conversion_stage == ConversionStage.NEW
                    )
                ).order_by(desc(Lead.opportunity_score)).limit(5)
            ).scalars().all()
        
        for lead_id in lead_ids:
            try:
                # IMPORTANT: Apply delay OUTSIDE of session block to prevent QueuePool overflow
                await human_engine.apply_randomized_delay("public_reply")

                with SessionLocal() as db:
                    lead = db.get(Lead, lead_id)
                    if not lead: continue

                    group = db.execute(select(Group).where(Group.id == lead.group_id)).scalar_one_or_none()
                    if not group: continue

                    # 1. Select persona for this lead (Module 5)
                    persona = power_upgrades_service.select_persona(lead)
                    response_text = await self.generate_public_response(lead.id, lead.original_message, persona)
                    
                    await human_engine.simulate_human_typing(client, group.telegram_id, len(response_text))

                    # Send the message (Module 9)
                    await client.send_message(group.telegram_id, response_text, reply_to=lead.telegram_message_id)

                    # Track account limit (Module 8)
                    if account:
                        await telegram_client_manager.track_account_limits(phone_number, "public_reply")

                    # Mark as sent and update CRM
                    lead.public_reply_sent = True
                    lead.last_contact = datetime.utcnow()
                    lead.first_contact = datetime.utcnow()
                    lead.conversion_stage = ConversionStage.CONTACTED
                    
                    # Log to Memory Engine (Module 15)
                    memory_engine.log_message_interaction(
                        user_id=lead.user_id,
                        group_id=group.id,
                        message_text=response_text,
                        message_type="public_reply"
                    )
                    
                    new_conv = LeadConversation(
                        lead_id=lead.id,
                        message=response_text,
                        sender=persona['name'],
                        timestamp=datetime.utcnow()
                    )
                    db.add(new_conv)
                    db.commit()
                    logger.info(f"[SLIE Human Engine] Public reply sent to lead {lead.username} using account {phone_number}")
            except Exception as e:
                logger.error(f"Error processing public reply for lead {lead_id}: {e}")

    async def process_private_dms(self):
        """
        Elite Module 4 & 8: Process and send private DMs to leads.
        Uses Human Behavior Engine for authorization and randomization.
        """
        if not human_engine.is_within_natural_active_hours():
            return

        # Authorization check (Daily Limits)
        if not await human_engine.authorize_action("dm"):
            return

        # Find an account that can send a DM (Module 8)
        account = await telegram_client_manager.rotate_account("dm")
        
        if account:
            client = await telegram_client_manager.get_client(phone_number=account.phone_number)
            phone_number = account.phone_number
        else:
            # Fallback to .env account if session string exists
            if self.settings.telegram_session_string:
                client = await telegram_client_manager.get_client()
                phone_number = self.settings.telegram_phone
            else:
                logger.info("No active Telegram accounts with remaining DM limits.")
                return

        with SessionLocal() as db:
            # Elite Module 14, 15 & 16: Prioritize Tier 1 leads for DM follow-up
            # Fully Autonomous Mode: Include HIGH and MEDIUM leads (User Request)
            
            min_wait = datetime.utcnow() - timedelta(minutes=15)
            last_wait = datetime.utcnow() - timedelta(minutes=30)
            
            lead_ids = db.execute(
                select(Lead.id).where(
                    and_(
                        Lead.priority_level.in_(["HIGH", "MEDIUM"]),
                        Lead.dm_sent == False,
                        Lead.conversion_stage.in_([ConversionStage.NEW, ConversionStage.CONTACTED]),
                        Lead.last_contact <= min_wait,
                        # Rule: Do not send DM if any contact (public or private) was within 30 minutes
                        (Lead.last_contact.is_(None) | (Lead.last_contact <= last_wait)),
                        # Rule: Stop if converted
                        Lead.conversion_stage != ConversionStage.CONVERTED
                    )
                ).order_by(desc(Lead.opportunity_score)).limit(5)
            ).scalars().all()

        for lead_id in lead_ids:
            try:
                # IMPORTANT: Apply delay OUTSIDE of session block to prevent QueuePool overflow
                await human_engine.apply_randomized_delay("dm")

                with SessionLocal() as db:
                    lead = db.get(Lead, lead_id)
                    if not lead: continue

                    dm_text = await self.generate_private_dm(lead)
                    
                    await human_engine.simulate_human_typing(client, lead.telegram_user_id, len(dm_text))

                    # Send the DM (Module 10)
                    await client.send_message(lead.telegram_user_id, dm_text)

                    # Track account limit (Module 8)
                    if account:
                        await telegram_client_manager.track_account_limits(phone_number, "dm")

                    # Mark as sent and update CRM
                    lead.dm_sent = True
                    lead.last_contact = datetime.utcnow()
                    lead.conversion_stage = ConversionStage.CONTACTED
                    
                    # Log to Memory Engine (Module 15)
                    memory_engine.log_message_interaction(
                        user_id=lead.user_id,
                        group_id=lead.group_id,
                        message_text=dm_text,
                        message_type="direct_message"
                    )
                    
                    # Store DM in conversation history (Module 10)
                    persona = power_upgrades_service.select_persona(lead)
                    new_conv = LeadConversation(
                        lead_id=lead.id,
                        message=dm_text,
                        sender=persona['name'],
                        timestamp=datetime.utcnow()
                    )
                    db.add(new_conv)
                    db.commit()
                    logger.info(f"[SLIE Human Engine] Private DM sent to lead {lead.username} using account {phone_number}")
            except Exception as e:
                logger.error(f"Error processing private DM for lead {lead_id}: {e}")

response_engine = ResponseEngine()
