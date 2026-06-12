import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import desc, and_, select
from app.db.session import SessionLocal
from app.models.lead import Lead, ConversionStage
from app.models.message_analysis import MessageAnalysis
from app.services.ai_service import ai_service
from app.services.crm import lead_crm_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)

COMPLAINT_KEYWORDS = [
    "iptv", "buffering", "not working", "server down", 
    "playlist error", "xtream login failed", "reseller", "panel"
]

URGENCY_KEYWORDS = [
    "not working", "server down", "help", "any fix", "recommend provider"
]

class LeadScoringEngine:
    def __init__(self):
        self.settings = get_settings()

    async def analyze_message_ai(self, message_id: str, message_text: str) -> dict:
        """
        STEP 4 — NLP CLASSIFICATION (Message Intelligence Engine)
        Classify message intent: complaint, help_request, general_discussion, advertisement.
        """
        prompt = f"""
        Classify the intent of this IPTV-related message from a Telegram group.
        
        Options:
        - complaint: User is frustrated, reporting issues (e.g., buffering, freezing, server down, not working).
        - help_request: User is asking for recommendations or how to set things up (e.g., "any good iptv?", "recommend provider").
        - general_discussion: Normal conversation about streaming, sports, or tech without immediate buyer intent.
        - advertisement: Promotional content, spam, or other sellers offering services (e.g., "DM for best IPTV", links to services).
        
        Return JSON format:
        {{
            "intent_type": "complaint" | "help_request" | "general_discussion" | "advertisement",
            "intent_score": number (0–10),
            "problem_type": string (e.g. "buffering", "recommendation", "technical"),
            "confidence": percentage (0.0 to 1.0)
        }}
        
        Message: {message_text}
        """
        
        try:
            # 1. AI CALL - OUTSIDE SESSION
            content = await ai_service.chat_completion(
                prompt=prompt,
                response_format="json_object"
            )
            
            if not content:
                return {"intent_type": "general_discussion", "intent_score": 0, "confidence": 0}

            result = json.loads(content)
            
            # 2. STORE IN DB - BRIEF SESSION
            with SessionLocal() as db:
                analysis = MessageAnalysis(
                    message_id=message_id,
                    classification=result.get("intent_score", 0),
                    problem_type=result.get("problem_type"),
                    confidence=result.get("confidence")
                )
                db.add(analysis)
                db.commit()
                
            return result
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return {"intent_type": "general_discussion", "intent_score": 0, "confidence": 0}

    async def calculate_predictive_buyer_score(self, lead_id: str, message_text: str) -> int:
        """
        Elite Multi-Layer Dynamic Scoring (Layer 1-5).
        Scores leads across 5 dimensions: Intent, Problem, Engagement, Recency, and Pattern.
        """
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if not lead: return 0
            user = lead.user

            # LAYER 1: Intent Score (0-40 points)
            intent_score = 0
            text = message_text.lower()
            
            # Very High Intent (+35 to +40)
            vhi_terms = [
                "recommend a provider", "recommend provider", "need a new iptv", 
                "looking for a replacement", "who has a trial", "any good provider",
                "looking for iptv", "suggest an iptv"
            ]
            # Medium Intent (+20 to +35)
            mi_terms = [
                "buffering", "freezing", "not working", "pricing", "cost", "how much",
                "any trial", "test account", "technical question", "how to setup"
            ]
            
            if any(term in text for term in vhi_terms):
                intent_score = 40
            elif any(term in text for term in mi_terms):
                intent_score = 30
            else:
                intent_score = 10
            
            # LAYER 2: Problem Severity (0-20 points)
            problem_score = 0
            # Major Problem (+20)
            major_probs = [
                "service completely down", "constant buffering", "account disabled", 
                "provider disappeared", "scammed", "no response from provider", "server down"
            ]
            if any(term in text for term in major_probs):
                problem_score = 20
            # Medium Problem (+10)
            elif any(term in text for term in ["buffering", "channel issues", "lagging", "freezing"]):
                problem_score = 10

            # LAYER 3: Engagement Score (0-15 points)
            engagement_score = 0
            if user:
                # Based on user's historical activity
                if user.message_frequency > 15:
                    engagement_score = 15
                elif user.message_frequency > 5:
                    engagement_score = 10
                elif user.message_frequency > 1:
                    engagement_score = 5

            # LAYER 4: Recency Score (0-15 points)
            # When a lead is first detected, it's "Today"
            recency_score = 15

            # LAYER 5: Buyer Pattern Score (0-10 points)
            pattern_score = 0
            # Positive Signals
            pos_patterns = ["trial", "price", "compare", "recommend", "recurring", "complaint"]
            if any(term in text for term in pos_patterns):
                pattern_score += 10
                
            # Negative Signals (Advertisers/Sellers) - Strong Penalty
            neg_patterns = [
                "dm me", "best service", "join my", "panel available", "reseller", 
                "best iptv", "whatsapp", "t.me/", "low price", "reliable service"
            ]
            if any(term in text for term in neg_patterns):
                pattern_score -= 60 # Massive penalty for potential sellers

            # UPDATE LEAD FIELDS
            lead.intent_score = float(intent_score)
            lead.urgency_score = float(problem_score)
            lead.engagement_score = float(engagement_score)
            lead.recency_score = float(recency_score)
            lead.pattern_score = float(pattern_score)
            
            # FINAL FORMULA
            total_score = intent_score + problem_score + engagement_score + recency_score + pattern_score
            total_score = max(0, min(100, total_score))
            
            lead.lead_score = int(total_score)
            lead.opportunity_score = float(total_score)
            
            # CATEGORIZE
            if total_score >= 80:
                lead.lead_temperature = "HOT"
                lead.priority_level = "HIGH"
            elif total_score >= 60:
                lead.lead_temperature = "WARM"
                lead.priority_level = "MEDIUM"
            elif total_score >= 40:
                lead.lead_temperature = "POTENTIAL"
                lead.priority_level = "LOW"
            else:
                lead.lead_temperature = "COLD"
                lead.priority_level = "IGNORE"

            db.commit()
            logger.info(f"[SLIE Dynamic Scoring] Lead {lead_id} scored {total_score} ({lead.lead_temperature})")
            return int(total_score)

    async def detect_pain_signals(self, text: str) -> dict:
        """
        Module 1: Pain Signal Detection.
        Extract specific pain points from user messages.
        """
        text = text.lower()
        signals = {
            "technical": [],
            "service": [],
            "financial": []
        }
        
        tech_pain = ["buffering", "freezing", "lag", "quality", "hd", "4k", "server"]
        service_pain = ["down", "offline", "unreliable", "scam", "disappeared", "no reply"]
        financial_pain = ["price", "cost", "expensive", "refund", "billing"]
        
        for term in tech_pain:
            if term in text: signals["technical"].append(term)
        for term in service_pain:
            if term in text: signals["service"].append(term)
        for term in financial_pain:
            if term in text: signals["financial"].append(term)
            
        return signals

    async def decay_lead_scores(self):
        """
        Elite Step: Buying intent expires. Decay recency score daily.
        Recalculates total score based on the 5-layer model.
        """
        with SessionLocal() as db:
            # Only decay leads that aren't already converted or disqualified
            leads = db.execute(
                select(Lead).where(
                    and_(
                        Lead.conversion_stage == ConversionStage.NEW,
                        Lead.lead_temperature != "IGNORE"
                    )
                )
            ).scalars().all()
            
            now = datetime.now(timezone.utc)
            for lead in leads:
                # Recalculate Recency Score based on timestamp
                delta = now - lead.timestamp
                days_old = delta.days
                
                if days_old == 0:
                    lead.recency_score = 15
                elif days_old <= 3:
                    lead.recency_score = 10
                elif days_old <= 7:
                    lead.recency_score = 5
                else:
                    lead.recency_score = 0
                
                # Recalculate Total Score
                total_score = (
                    lead.intent_score + 
                    lead.urgency_score + 
                    lead.engagement_score + 
                    lead.recency_score + 
                    lead.pattern_score
                )
                total_score = max(0, min(100, total_score))
                
                lead.lead_score = int(total_score)
                lead.opportunity_score = float(total_score)
                
                # Update Temperature
                if total_score >= 80:
                    lead.lead_temperature = "HOT"
                elif total_score >= 60:
                    lead.lead_temperature = "WARM"
                elif total_score >= 40:
                    lead.lead_temperature = "POTENTIAL"
                else:
                    lead.lead_temperature = "COLD"
            
            db.commit()
            logger.info(f"[SLIE Decay] Decayed scores for {len(leads)} leads.")

    async def get_top_intent_buyers(self, limit: int = 20, days: int = 7) -> List[Lead]:
        """
        Returns the highest-intent buyers detected in the last N days.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        with SessionLocal() as db:
            stmt = select(Lead).where(
                and_(
                    Lead.timestamp >= since,
                    Lead.lead_temperature.in_(["HOT", "WARM"])
                )
            ).order_by(desc(Lead.lead_score)).limit(limit)
            
            leads = db.execute(stmt).scalars().all()
            return list(leads)

    async def calculate_lead_score(self, lead_id: str, message_text: str, _ai_result: dict = None) -> tuple[int, str]:
        """
        Unified scoring entry point.
        """
        score = await self.calculate_predictive_buyer_score(lead_id, message_text)
        
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if lead:
                return lead.lead_score, lead.lead_temperature or "COLD"
        return score, "COLD"

    async def create_lead(self, user_id: int, username: str, group_id: str, message_text: str, _message_id: str = None, ai_analysis: dict = None, _pain_signals: dict = None):
        """
        Performs full pipeline: Analyze -> Score -> Create Lead
        """
        # 0. Prevent duplicate contact
        if lead_crm_service.is_already_contacted(user_id):
            logger.info(f"Skipping duplicate contact for user {user_id}")
            return None

        # 1. Get or Create Lead
        with SessionLocal() as db:
            from app.models.user import User
            user = db.execute(select(User).where(User.telegram_user_id == user_id)).scalar_one_or_none()
            if not user:
                return None

            existing_lead = db.execute(
                select(Lead).where(
                    and_(
                        Lead.user_id == user.id,
                        Lead.conversion_stage == ConversionStage.NEW
                    )
                )
            ).scalar_one_or_none()
            
            if existing_lead:
                lead = existing_lead
            else:
                lead = Lead(
                    user_id=user.id,
                    group_id=group_id,
                    message_text=message_text,
                    timestamp=datetime.now(timezone.utc),
                    conversion_stage=ConversionStage.NEW
                )
                db.add(lead)
                db.flush()
            
            if ai_analysis:
                lead.intent_type = ai_analysis.get("intent_type")
            
            lead_id = lead.id
            db.commit()

        # 2. Score Lead
        await self.calculate_predictive_buyer_score(lead_id, message_text)

        # 3. Store initial history
        with SessionLocal() as db:
            from app.models.lead_conversation import LeadConversation
            lead = db.get(Lead, lead_id)
            if lead:
                new_conv = LeadConversation(
                    lead_id=lead.id,
                    message=message_text,
                    sender="User",
                    timestamp=datetime.now(timezone.utc)
                )
                db.add(new_conv)
                db.commit()
                db.refresh(lead)
                
                logger.info(f"[SLIE Lead Engine] Lead processed: {username} (Score: {lead.lead_score})")
                return lead
        return None

lead_scoring = LeadScoringEngine()
lead_scoring_engine = lead_scoring

# Exportable functions for compatibility
async def calculate_lead_score(lead_id: str, message_text: str):
    return await lead_scoring.calculate_lead_score(lead_id, message_text)

async def create_lead(user_id: int, username: str, group_id: str, message: str, ai_analysis: dict = None, pain_signals: dict = None):
    return await lead_scoring.create_lead(user_id, username, group_id, message, ai_analysis=ai_analysis, pain_signals=pain_signals)

async def get_top_leads(limit: int = 20, days: int = 7):
    return await lead_scoring.get_top_intent_buyers(limit, days)
