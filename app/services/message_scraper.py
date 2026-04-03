import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional

import emoji
from sqlalchemy import select, desc
from telethon import events, types

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.message import Message
from app.services.telegram_client import telegram_client_manager

from app.services.group_discovery.invite_link_extractor import handle_message_for_invite_links
from app.services.memory_engine import memory_engine
from app.services.power_upgrades import power_upgrades_service

logger = logging.getLogger(__name__)

SPAM_PHRASES = [
    "buy now", "cheap iptv", "promo", "contact admin"
]

MESSAGE_URL_PATTERN = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
INVITE_HINTS = ("t.me/", "telegram.me/", "joinchat", "t.me/+")
DEEP_ANALYSIS_KEYWORDS = {
    "iptv",
    "buffering",
    "freezing",
    "lag",
    "server down",
    "not working",
    "trial",
    "reseller",
    "panel",
    "m3u",
    "xtream",
    "portal",
    "recommend",
    "provider",
    "setup",
    "help",
    "fix",
    "price",
}

from app.services.response_engine import response_engine, AIDEN_SYSTEM_PROMPT
from app.services.ai_service import ai_service
from app.models.lead import Lead
from app.models.lead_conversation import LeadConversation
from app.models.enums import ConversionStage

class MessageScraper:
    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._listener_started = False
        self._admin_status_cache: dict[tuple[int, int], tuple[datetime, bool]] = {}
        self._analysis_semaphore = asyncio.Semaphore(max(1, self.settings.max_message_analysis_concurrency))

    async def generate_ai_reply(self, lead: Lead, message_text: str) -> str:
        """
        Elite Module 10: AI Conversation Auto-Closer.
        Automatically continue DM conversations with leads toward conversion.
        """
        # Select persona for this lead (Module 5)
        persona = power_upgrades_service.select_persona(lead)
        
        system_prompt = f"""
        You are {persona['name']}, {persona['role']} for Streamexpert. 
        You are an IPTV infrastructure specialist helping users solve streaming issues.
        Expertise: {persona['expertise']}
        Tone: {persona['tone']}
        
        OBJECTIVE:
        Automatically continue DM conversations with leads.
        Provide helpful technical explanations and guide users toward reseller panels or premium IPTV services.
        
        COMMON QUESTIONS TO HANDLE:
        - price
        - trial
        - reseller panel
        - device compatibility
        - setup help

        RULES: 
        - be helpful
        - avoid aggressive sales language
        - end responses with a question to continue conversation
        - 50-80 words, 4-5 sentences.
        - max 2 emojis 🤝 📺 💎 
        """

        # Fetch conversation history for this lead
        history_text = ""
        with SessionLocal() as db:
            recent_convs = db.execute(
                select(LeadConversation)
                .where(LeadConversation.lead_id == lead.id)
                .order_by(desc(LeadConversation.timestamp))
                .limit(5)
            ).scalars().all()
            
            # Reverse history to be chronological for the AI
            for conv in reversed(recent_convs):
                history_text += f"{conv.sender}: {conv.message}\n"
        
        prompt = f"Lead Conversation History:\n{history_text}\n\nNew Lead Message: {message_text}\n\nContinue the conversation as {persona['name']}, providing technical help and guiding the user toward a solution."
        
        try:
            content = await ai_service.chat_completion(
                prompt=prompt,
                system_prompt=system_prompt
            )
            return content if content else f"That's a valid technical concern. As a {persona['role']}, I'd like to provide a detailed explanation of how our infrastructure handles that. Would you like a trial to test our compatibility directly? 🤝"
        except Exception as e:
            logger.error(f"Error generating AI reply: {e}")
            return "I'm reviewing the technical specifications for that request. Most device compatibility issues are resolved through our custom panels. Shall we set up a quick test for you? 📺"

    def filter_message_noise(self, message) -> bool:
        """
        STEP 2 — NOISE FILTERING (Message Intelligence Engine)
        Ignore messages that are low value.
        """
        # Handle both Telethon event objects and raw strings
        if hasattr(message, 'message'):
            message_text = message.message or ""
        else:
            message_text = str(message)

        text = message_text.strip()
        
        # 1. message length < 5 characters
        if len(text) < 5:
            return False
            
        # 2. message contains only emojis
        if not emoji.replace_emoji(text, "").strip():
            return False
            
        # 3. message contains only URLs
        text_no_urls = MESSAGE_URL_PATTERN.sub("", text).strip()
        if not text_no_urls:
            return False
            
        return True

    def _contains_possible_invite_link(self, message_text: str) -> bool:
        if not message_text:
            return False
        lower_text = message_text.lower()
        return any(hint in lower_text for hint in INVITE_HINTS)

    def _should_run_deep_analysis(self, message_text: str) -> bool:
        if not message_text:
            return False

        lowered = message_text.lower()
        if "?" in lowered:
            return True

        return any(keyword in lowered for keyword in DEEP_ANALYSIS_KEYWORDS)

    async def _is_group_admin(self, event, sender) -> bool:
        if not sender:
            return False

        cache_key = (event.chat_id, sender.id)
        cached = self._admin_status_cache.get(cache_key)
        now = datetime.utcnow()
        if cached and cached[0] > now:
            return cached[1]

        is_admin = False
        try:
            permissions = await event.client.get_permissions(event.chat_id, sender.id)
            is_admin = bool(getattr(permissions, "is_admin", False))
        except Exception as e:
            logger.debug(f"Could not check admin permissions for user {sender.id}: {e}")

        expires_at = now + timedelta(seconds=self.settings.admin_cache_ttl_seconds)
        self._admin_status_cache[cache_key] = (expires_at, is_admin)
        return is_admin

    def _extract_pain_signals(self, message_text: str) -> dict[str, list[str]]:
        lowered = message_text.lower()
        pain_signals = {
            "complaints": [term for term in ("buffering", "freezing", "not working", "server down", "lag", "error") if term in lowered],
            "buyer_intent": [term for term in ("recommend", "trial", "provider", "reseller", "panel", "price") if term in lowered],
            "technical_terms": [term for term in ("xtream", "m3u", "portal", "dns", "setup") if term in lowered],
        }
        return pain_signals

    async def start_message_listener(self):
        """
        Starts the real-time message listener for all joined groups.
        Captures new messages and saves them to the database.
        """
        if self._listener_started:
            logger.info("Message listener already initialized; skipping duplicate registration.")
            return

        self._client = await telegram_client_manager.get_client()
        
        @self._client.on(events.NewMessage)
        async def handler(event):
            # 1. Check if it's a Private Message (Direct Response from Lead)
            if event.is_private:
                await self._handle_private_message(event)
                return

            # 2. Listen only to groups/channels (joined groups)
            if not (event.is_group or event.is_channel):
                return

            if not getattr(event, "message", None):
                return

            message_text = event.message.message or ""

            # STEP 2: INVITE LINK EXTRACTION (Continuous Discovery)
            if self._contains_possible_invite_link(message_text):
                await handle_message_for_invite_links(event)
            
            # 2. Elite Module 1: Noise Filtering
            if not self.filter_message_noise(event):
                return

            # 4. Apply Safety Rules (Module 11 & Safety Requirements)
            # - Never message bots
            # - Never message admins
            # - Never contact same user twice (handled in lead_scoring.create_lead)
            sender = await event.get_sender()
            if not sender or getattr(sender, 'bot', False):
                return
                
            # System message check
            if isinstance(event.message.action, (types.MessageActionChatAddUser, 
                                                 types.MessageActionChatDeleteUser,
                                                 types.MessageActionChatEditTitle)):
                return

            # Admin check (Safety Rule)
            if await self._is_group_admin(event, sender):
                logger.debug(f"Skipping message from admin: {sender.id} in group {event.chat_id}")
                with SessionLocal() as db:
                    lead = db.execute(select(Lead).where(Lead.telegram_user_id == sender.id)).scalar_one_or_none()
                    if lead:
                        lead.is_admin = True
                        lead.influence_level = "admin"
                        db.commit()
                return

            # 5. Save the message
            await self.save_message(event, sender)

        self._listener_started = True
        logger.info("Message listener started. Capturing messages from joined groups...")
        # Note: run_until_disconnected() is usually handled in the main loop or a dedicated task.

    async def _handle_private_message(self, event):
        """
        Elite Module 10: Handle inbound DMs from leads with AI Handler and Persona Rotation.
        Uses account rotation and limit tracking (Module 8).
        """
        sender = await event.get_sender()
        if not sender or getattr(sender, 'bot', False):
            return

        message_text = event.message.message or ""
        
        # 1. Update status and log inbound message
        with SessionLocal() as db:
            # Check if this user is a lead in our system
            lead = db.execute(
                select(Lead).where(Lead.telegram_user_id == sender.id)
            ).scalar_one_or_none()
            
            if not lead:
                return # We only auto-reply to known leads we contacted first

            # Update Lead Status
            lead.conversion_stage = ConversionStage.RESPONDED
            lead.last_contact = datetime.utcnow()

            # Store lead's message in history
            lead_msg = LeadConversation(
                lead_id=lead.id,
                message=message_text,
                sender="User",
                timestamp=datetime.utcnow()
            )
            db.add(lead_msg)
            
            # Log to Memory Engine (Module 15)
            memory_engine.log_message_interaction(
                user_id=lead.user_id,
                group_id=None,
                message_text=message_text,
                message_type="user_reply"
            )
            
            db.commit()
            # Capture lead.id before closing session
            lead_id = lead.id

        # 2. Find an account that can send a DM (Module 8) - OUTSIDE DB SESSION
        account = await telegram_client_manager.rotate_account("dm")
        if not account:
            logger.warning("No accounts available to send DM reply.")
            return

        client = await telegram_client_manager.get_client(phone_number=account.phone_number)

        # 3. Generate AI Response (Module 10) - OUTSIDE DB SESSION
        # Re-fetch lead for persona selection (generate_ai_reply handles its own session for history)
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            reply_text = await self.generate_ai_reply(lead, message_text)

        # 4. Apply DM simulation behavior (Module 4) - OUTSIDE DB SESSION
        # Typing delay: 3-10s
        await response_engine.simulate_typing(client, sender.id)

        # 5. Send the AI response - OUTSIDE DB SESSION
        await client.send_message(sender.id, reply_text)

        # 6. Final logging and tracking - NEW SESSIONS
        memory_engine.log_message_interaction(
            user_id=lead.user_id,
            group_id=None,
            message_text=reply_text,
            message_type="dm_message"
        )

        # Track account limit (Module 8)
        await telegram_client_manager.track_account_limits(account.phone_number, "dm")

        # Store AI response in history
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            persona = power_upgrades_service.select_persona(lead)
            ai_msg = LeadConversation(
                lead_id=lead.id,
                message=reply_text,
                sender=persona['name'],
                timestamp=datetime.utcnow()
            )
            db.add(ai_msg)
            db.commit()
            
        logger.info(
            "AI response sent to lead %s using account %s",
            sender.id,
            account.phone_number,
        )

    async def save_message(self, event, sender):
        """
        STEP 1 — MESSAGE COLLECTION (Message Intelligence Engine)
        Persists a captured Telegram message and runs intelligence analysis.
        """
        from app.services.lead_scoring import lead_scoring_engine
        from app.models.user import User
        from app.models.group import Group
        from app.models.cross_group_identity import CrossGroupIdentity
        from app.intelligence.services.influence_service import influence_engine
        from app.intelligence.services.competitor_service import competitor_scanner
        from app.intelligence.services.conversion_service import conversion_engine
        from sqlalchemy import func

        try:
            message_text = event.message.message or ""
            if not message_text:
                return
            telegram_user_id = sender.id
            chat_id = event.chat_id

            # 1. INITIAL DB OPERATIONS: Check duplicate, Update/Create User, Save Message
            with SessionLocal() as db:
                # Check for duplicates
                existing = db.execute(
                    select(Message).where(
                        Message.telegram_id == event.message.id,
                        Message.telegram_group_id == chat_id
                    )
                ).scalar_one_or_none()
                if existing:
                    return

                # Get or Create Global User Profile (Step 6)
                user = db.execute(
                    select(User).where(User.telegram_user_id == telegram_user_id)
                ).scalar_one_or_none()
                
                if not user:
                    user = User(
                        telegram_user_id=telegram_user_id,
                        username=getattr(sender, 'username', None),
                        first_seen=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                        groups_seen=0,
                        messages_today=0,
                        message_frequency=0,
                        complaints_count=0,
                        technical_questions_count=0
                    )
                    db.add(user)
                    db.flush()

                # Update User activity metrics
                today = datetime.utcnow().date()
                last_seen_date = user.last_seen.date() if user.last_seen else None
                user.last_seen = datetime.utcnow()
                user.message_frequency += 1
                
                if last_seen_date == today:
                    user.messages_today += 1
                else:
                    user.messages_today = 1
                
                group = db.execute(select(Group).where(Group.telegram_id == chat_id)).scalar_one_or_none()
                group_id = group.id if group else None

                if group_id:
                    identity = db.execute(
                        select(CrossGroupIdentity).where(
                            CrossGroupIdentity.user_id == user.id,
                            CrossGroupIdentity.group_id == group_id
                        )
                    ).scalar_one_or_none()

                    if not identity:
                        identity = CrossGroupIdentity(
                            user_id=user.id,
                            group_id=group_id,
                            first_seen_in_group=datetime.utcnow(),
                            last_seen_in_group=datetime.utcnow()
                        )
                        db.add(identity)
                        user.groups_seen += 1
                    else:
                        identity.last_seen_in_group = datetime.utcnow()
                
                # Save raw message
                new_msg = Message(
                    telegram_id=event.message.id,
                    telegram_message_id=event.message.id,
                    telegram_group_id=chat_id,
                    telegram_user_id=telegram_user_id,
                    username=user.username,
                    reply_to_message_id=event.message.reply_to_msg_id if hasattr(event.message, 'reply_to_msg_id') else None,
                    body=message_text,
                    sent_at=event.message.date,
                    reply_count=event.message.replies.replies if event.message.replies else 0
                )
                db.add(new_msg)
                db.flush()
                
                # Capture IDs for later use
                message_id = new_msg.id
                user_id = user.id
                
                # Influence Graph Update
                if group_id and (not self.settings.low_cpu_mode or user.messages_today % 10 == 0):
                    influence_engine.update_influence_score(user.id, group_id)
                
                db.commit()

            if not self._should_run_deep_analysis(message_text):
                return

            # 2. ASYNC AI ANALYSIS: Detect Pain Signals and Analyze AI - OUTSIDE DB SESSION
            pain_signals = self._extract_pain_signals(message_text)
            has_pain = any(len(v) > 0 for v in pain_signals.values())

            if has_pain or not self.settings.low_cpu_mode:
                # Perform long-running AI analysis outside the session
                async with self._analysis_semaphore:
                    ai_result = await lead_scoring_engine.analyze_message_ai(str(message_id), message_text)

                intent_type = ai_result.get("intent_type", "general_discussion")

                if intent_type not in {"complaint", "help_request"} and not has_pain:
                    return

                # 3. FINAL DB UPDATES: Update User metrics and Lead Creation - NEW SESSION
                should_run_competitor_scan = False
                with SessionLocal() as db:
                    user = db.get(User, user_id)
                    if not user:
                        return
                    
                    if intent_type == "complaint":
                        user.complaints_count += 1
                        should_run_competitor_scan = True
                    elif intent_type == "help_request":
                        user.technical_questions_count += 1

                    db.commit()

                if should_run_competitor_scan and not self.settings.low_cpu_mode:
                    await competitor_scanner.analyze_message_for_competitors(message_text)

                await lead_scoring_engine.create_lead(
                    user_id=telegram_user_id,
                    username=getattr(sender, "username", None),
                    group_id=group_id,
                    message_text=message_text,
                    message_id=message_id,
                    ai_analysis=ai_result,
                    pain_signals=pain_signals
                )

            # Community conversion tracking
            if has_pain or not self.settings.low_cpu_mode:
                await conversion_engine.track_message_conversion_potential(message_id, message_text)
        except Exception as e:
            logger.error(f"Error in Message Intelligence Engine: {e}")

    async def get_recent_messages(self, limit: int = 50) -> List[Message]:
        """
        Retrieves the most recent scraped messages from the database.
        """
        with SessionLocal() as db:
            result = db.execute(
                select(Message)
                .where(Message.telegram_id != None)
                .order_by(desc(Message.sent_at))
                .limit(limit)
            ).scalars().all()
            return list(result)

message_scraper = MessageScraper()

# Exportable functions as per requirements
async def start_message_listener():
    await message_scraper.start_message_listener()

async def save_message(event, sender):
    await message_scraper.save_message(event, sender)

async def get_recent_messages(limit: int = 50):
    return await message_scraper.get_recent_messages(limit)
