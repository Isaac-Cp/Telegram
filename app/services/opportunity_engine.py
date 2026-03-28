import logging
import json
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.models.message import Message
from app.models.lead_opportunity import LeadOpportunity
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class OpportunityScoringEngine:
    """
    MODULE 1 — LEAD OPPORTUNITY SCORING ENGINE
    Determine which detected leads represent the best sales opportunities.
    """

    async def calculate_intent_score(self, message_text: str) -> int:
        """
        Measures how strongly the user appears to want a new IPTV service.
        Signals: complaints about provider, requests for recommendations, reliability questions.
        """
        prompt = f"""
        Analyze the purchase intent for a new IPTV service from this message.
        Rate intent from 1 to 10.
        
        High Score (8-10): Explicitly asking for recommendations, trial, or reporting major failure of current provider.
        Medium Score (4-7): Asking technical questions or comparing services.
        Low Score (1-3): General chat or vague interest.

        MESSAGE: {message_text}
        
        Return JSON format: {{"intent_score": int}}
        """
        try:
            content = await ai_service.chat_completion(prompt=prompt, response_format="json_object")
            data = json.loads(content) if content else {}
            score = data.get("intent_score", 1)
            return max(1, min(10, score))
        except Exception as e:
            logger.error(f"[SLIE Opportunity Engine] Error calculating intent score: {e}")
            return 1

    def calculate_urgency_score(self, lead: Lead, message_text: str, db: Session) -> int:
        """
        Measures whether the user needs a solution immediately.
        Signals: frustrated language, repeated complaints, multiple messages in short time frame.
        """
        score = 1
        text_lower = message_text.lower()
        
        # 1. Frustrated language
        if any(kw in text_lower for kw in ["urgent", "now", "asap", "immediately", "down", "broken", "help"]):
            score += 4
            
        # 2. Activity spike (Module 1 Step 4)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_count = db.query(func.count(Message.id)).filter(
            Message.telegram_user_id == lead.user.telegram_user_id,
            Message.sent_at >= one_hour_ago
        ).scalar() or 0
        
        if recent_count > 3:
            score += 3
            
        # 3. Repeated complaints (from user profile)
        if lead.user.complaints_count > 1:
            score += 2
            
        return max(1, min(10, score))

    def calculate_influence_score(self, user: User) -> int:
        """
        Measures the user's influence inside the community.
        Signals: message frequency, engagement, helping others, admin/mod role.
        """
        score = 2 # Baseline
        
        if user.is_admin:
            score = 10
        elif user.is_power_user:
            score = 7
        elif (user.message_frequency or 0) > 50:
            score = 5
            
        # Engagement/Help signal (Module 1 Influence)
        if (user.technical_questions_count or 0) > 5:
            score = max(score, 6)
            
        return max(1, min(10, score))

    def calculate_activity_score(self, user: User) -> int:
        """
        Measures the user's activity level.
        Signals: message frequency.
        """
        # Scale 1-10: 100+ messages = 10, 0 messages = 1
        freq = user.message_frequency or 0
        score = min(10, (freq // 10) + 1)
        return score

    async def score_lead(self, lead_id: str) -> Tuple[float, str]:
        """
        Calculate an opportunity_score using weighted factors (Master Prompt Step 9).
        Output: opportunity_score (0-10), priority_level (HIGH, MEDIUM, LOW)
        """
        # 1. Fetch initial data - BRIEF SESSION
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if not lead or not lead.user:
                return 0.0, "LOW"
            
            original_message = lead.original_message
            user_id = lead.user.id
            # Capture user object for synchronous calculation
            user = lead.user
            
            # 2. Urgency Score (30% weight) - SYNCHRONOUS
            urgency_score = self.calculate_urgency_score(lead, original_message, db)
            
            # 3. Activity Score (20% weight) - SYNCHRONOUS
            activity_score = self.calculate_activity_score(user)

        # 4. Intent Score (50% weight) - ASYNC AI CALL (OUTSIDE SESSION)
        intent_score = await self.calculate_intent_score(original_message)
        
        # SCORING MODEL (Master Prompt Step 9)
        opportunity_score = (intent_score * 0.5) + (urgency_score * 0.3) + (activity_score * 0.2)
        opportunity_score = round(max(0.0, min(10.0, opportunity_score)), 2)
        
        # PRIORITY LOGIC (Master Prompt Step 9)
        if opportunity_score >= 7.5:
            priority = "HIGH"
        elif opportunity_score >= 5.0:
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        # 5. Final Update - NEW BRIEF SESSION
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if lead:
                lead.opportunity_score = opportunity_score
                lead.priority_level = priority
                
                # Save detailed metrics to LeadOpportunity
                opp = db.execute(select(LeadOpportunity).where(LeadOpportunity.lead_id == lead.id)).scalar_one_or_none()
                if not opp:
                    opp = LeadOpportunity(lead_id=lead.id)
                    db.add(opp)
                
                opp.intent_score = intent_score
                opp.urgency_score = urgency_score
                opp.opportunity_score = opportunity_score
                opp.priority_level = priority
                
                db.commit()
                logger.info(f"[SLIE Opportunity Engine] high priority lead detected: {lead.id} - Score: {opportunity_score}")
                
        return opportunity_score, priority

opportunity_engine = OpportunityScoringEngine()
