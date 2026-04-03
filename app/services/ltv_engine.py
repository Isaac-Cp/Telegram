import logging
from datetime import datetime
from typing import Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.user import User
from app.models.conversation_memory import LeadValueScore, UnifiedConversation
from app.services.opportunity_engine import opportunity_engine

logger = logging.getLogger(__name__)

# Module 2 Signals
TECHNICAL_EXPERT_KEYWORDS = ["xtream", "panel", "credits", "server access", "reseller panel", "m3u", "portal", "dns"]
RESELLER_KEYWORDS = ["credits", "reseller", "panel", "wholesale", "bulk", "sell iptv"]

class LeadLifetimeValueEngine:
    """
    MODULE 2 — LEAD LIFETIME VALUE ENGINE
    Estimate the long-term revenue potential of a lead.
    """

    def calculate_ltv_score(self, user_id: str) -> Tuple[float, str]:
        """
        Analyze conversation data and user signals to compute LTV score (0-10) and tier.
        """
        with SessionLocal() as db:
            lead = db.get(Lead, user_id)
            if not lead or not lead.user:
                return 0.0, "STANDARD BUYER"

            user = lead.user

            # 1. Technical Knowledge (0-10)
            tech_match = self._count_keyword_matches(user.id, TECHNICAL_EXPERT_KEYWORDS, db)
            tech_score = min(10.0, tech_match * 1.5) # ~7 matches for max score
            
            # 2. Community Influence (0-10)
            # Reusing Module 1's influence score as it captures admin/help signals
            influence_score = opportunity_engine.calculate_influence_score(user)
            
            # 3. Multi-Group Presence & Activity Frequency (0-10)
            # Multi-group bonus (Step 3 Module 2)
            group_bonus = min(10.0, user.groups_seen * 2.0) # 5 groups = 10 pts
            activity_score = min(10.0, (user.message_frequency / 20.0) * 10.0) # 20 msgs = 10 pts
            frequency_score = (group_bonus * 0.6) + (activity_score * 0.4)
            
            # 4. Conversation Engagement (0-10)
            # Based on UnifiedConversation entries
            total_interactions = db.query(func.count(UnifiedConversation.id)).filter(
                UnifiedConversation.user_id == user.id
            ).scalar() or 0
            engagement_score = min(10.0, (total_interactions / 10.0) * 10.0) # 10 interactions = 10 pts

            # SCORING MODEL (Master Prompt Step 10)
            # ltv_score = (technical_keywords * 0.4) + (group_influence * 0.3) + (activity_frequency * 0.3)
            ltv_score = (tech_score * 0.4) + (influence_score * 0.3) + (frequency_score * 0.3)
            ltv_score = round(max(0.0, min(10.0, ltv_score)), 2)

            # LTV TIER LOGIC (Master Prompt Step 10)
            if ltv_score >= 8.0:
                tier = "RESELLER POTENTIAL"
            elif ltv_score >= 5.0:
                tier = "HIGH VALUE BUYER"
            else:
                tier = "STANDARD BUYER"

            # Save to DB
            score_record = db.execute(
                select(LeadValueScore).where(LeadValueScore.user_id == user.id)
            ).scalar_one_or_none()
            
            if not score_record:
                score_record = LeadValueScore(user_id=user.id)
                db.add(score_record)
            
            score_record.ltv_score = ltv_score
            score_record.ltv_tier = tier
            score_record.last_updated = datetime.utcnow()
            
            db.commit()
            
            # MODULE 10 — LOGGING (Master Prompt Step 10)
            if tier == "RESELLER POTENTIAL":
                logger.info(f"[SLIE LTV Engine] high value lead detected: {user.id} - Tier: {tier}")
            else:
                logger.info(f"[SLIE LTV Engine] Lead LTV calculated: {user.id} - Score: {ltv_score} (Tier: {tier})")
                
            return ltv_score, tier

    def _count_keyword_matches(self, user_id: str, keywords: list[str], db: Session) -> int:
        """Helper to count keyword occurrences in user messages."""
        count = 0
        messages = db.execute(
            select(UnifiedConversation.message_text).where(
                UnifiedConversation.user_id == user_id,
                UnifiedConversation.message_type.in_(["user_reply", "group_message"])
            )
        ).scalars().all()
        
        for msg in messages:
            text = msg.lower()
            for kw in keywords:
                if kw in text:
                    count += 1
        return count

    async def recalculate_all_scores(self):
        """Automation: Recalculate LTV score for all active leads every 24 hours."""
        logger.info("[SLIE LTV Engine] Starting bulk recalculation...")
        with SessionLocal() as db:
            leads = db.query(Lead.id).all()
            for (lead_id,) in leads:
                self.calculate_ltv_score(lead_id)
        logger.info("[SLIE LTV Engine] Bulk recalculation completed.")

ltv_engine = LeadLifetimeValueEngine()
