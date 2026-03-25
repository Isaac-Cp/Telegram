import logging
from datetime import datetime
from slie.core.database import AsyncSessionLocal
from slie.models.conversation_models import Message
from slie.models.lead_models import User, Lead
from slie.intelligence.pain_signal_detector import pain_detector
from sqlalchemy import select

logger = logging.getLogger(__name__)

class MessageIntelligenceEngine:
    """
    STEP 7: MESSAGE INTELLIGENCE ENGINE
    Monitor group messages. Extract signals and store in database.
    """

    async def process_message(self, event):
        """Process incoming Telegram message event."""
        if not event.message or not event.message.text:
            return

        body = event.message.text
        telegram_group_id = event.chat_id
        telegram_user_id = event.sender_id
        
        # 1. Store Message in DB
        async with AsyncSessionLocal() as db:
            # Get or create user
            user_stmt = select(User).where(User.telegram_user_id == telegram_user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                sender = await event.get_sender()
                username = getattr(sender, 'username', None)
                user = User(
                    telegram_user_id=telegram_user_id,
                    username=username,
                    first_seen=datetime.utcnow()
                )
                db.add(user)
                await db.flush() # Get user.id

            # Store message
            new_msg = Message(
                telegram_id=event.message.id,
                telegram_message_id=event.message.id,
                telegram_group_id=telegram_group_id,
                telegram_user_id=telegram_user_id,
                username=user.username,
                body=body,
                sent_at=event.message.date or datetime.utcnow()
            )
            db.add(new_msg)
            
            # 2. Extract Pain Signals (Step 8)
            classification, intent_score = await pain_detector.classify_message(body)
            
            # 3. If intent is high, create/update Lead
            if intent_score > 0:
                logger.info(f"[SLIE Message Intelligence] Lead detected: {user.username} - Intent: {classification} ({intent_score})")
                
                # Check for urgency keywords
                urgency_score = self._calculate_urgency(body)
                
                lead = Lead(
                    user_id=user.id,
                    group_id=None, # Will be set if group is tracked
                    message_text=body,
                    intent_score=intent_score,
                    urgency_score=urgency_score,
                    priority_level="LOW" # Will be updated by scoring engine
                )
                db.add(lead)
            
            await db.commit()

    def _calculate_urgency(self, text: str) -> float:
        """Calculate urgency score based on keywords."""
        text = text.lower()
        urgency_keywords = ["now", "urgent", "asap", "quickly", "immediately", "help fast", "broken", "down"]
        score = 0.0
        for kw in urgency_keywords:
            if kw in text:
                score += 15.0
        return min(score, 100.0)

message_intelligence = MessageIntelligenceEngine()
