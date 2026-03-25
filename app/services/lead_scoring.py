import logging
import json
from datetime import datetime
import asyncio
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc, and_
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.message import Message
from app.models.message_analysis import MessageAnalysis
from app.models.lead_conversation import LeadConversation
from app.models.enums import ConversionStage
from app.services.crm import lead_crm_service
from app.services.ai_service import ai_service
from app.services.power_upgrades import power_upgrades_service
from app.services.opportunity_engine import opportunity_engine
from app.services.memory_engine import memory_engine
from app.services.ltv_engine import ltv_engine

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
            content = await ai_service.chat_completion(
                prompt=prompt,
                response_format="json_object"
            )
            
            if not content:
                return {"intent_type": "general_discussion", "intent_score": 0, "confidence": 0}

            result = json.loads(content)
            
            # Store in DB (Module 6 - SLIE Elite)
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

    async def detect_pain_signals(self, message_text: str) -> dict:
        """
        STEP 3 — PAIN SIGNAL DETECTION (Message Intelligence Engine)
        Categorize keywords into Frustration, Help Requests, and Technical Issues.
        """
        text = message_text.lower()
        signals = {
            "frustration": ["buffering", "lagging", "freezing", "server down", "not working"],
            "help_requests": ["any good iptv", "recommend provider", "iptv suggestion", "best iptv service"],
            "technical_issues": ["xtream", "panel", "server location", "stream quality"]
        }
        
        detected = {cat: [kw for kw in kws if kw in text] for cat, kws in signals.items()}
        return detected

    async def calculate_predictive_buyer_score(self, user_uuid: str, message_text: str) -> int:
        """
        Elite Module 5: Predictive Buyer Engine.
        Predict which users will likely buy IPTV soon based on signals.
        Enhanced with Cross-Group Identity Tracking (Elite Module 4).
        """
        score = 0
        text = message_text.lower()
        
        # 1. Complaint Signal (30 pts)
        complaint_terms = ["not working", "buffering", "lagging", "error", "down", "freezing"]
        if any(term in text for term in complaint_terms):
            score += 30
            
        # 2. Recommendation Request (40 pts)
        rec_terms = ["recommend", "any good", "best provider", "looking for", "suggest", "trial"]
        if any(term in text for term in rec_terms):
            score += 40
            
        # 3. Technical Terms (20 pts)
        tech_terms = ["xtream", "m3u", "panel", "dns", "portal", "vpn", "hosting", "server"]
        if any(term in text for term in tech_terms):
            score += 20
            
        # 4. Activity Spike (10 pts - based on last 10 messages)
        from app.models.message import Message
        from app.models.user import User
        from datetime import timedelta
        with SessionLocal() as db:
            user = db.get(User, user_uuid)
            if user:
                recent_count = db.query(Message).filter(
                    Message.telegram_user_id == user.telegram_user_id,
                    Message.sent_at >= datetime.utcnow() - timedelta(hours=1)
                ).count()
                if recent_count > 3: # More than 3 messages in an hour
                    score += 10
                
                # STEP 5 — PROFILE AGGREGATION (Module 4 Step 5)
                # Boost score based on cross-group presence and historical complaints
                if user.groups_seen > 1:
                    # +5 points for every additional group seen in, up to 20 points
                    group_bonus = min((user.groups_seen - 1) * 5, 20)
                    score += group_bonus
                    logger.debug(f"[Identity Tracking] User {user.username} seen in {user.groups_seen} groups. Group Bonus: +{group_bonus}")

                if user.complaints_count > 1:
                    # +10 points for recurring complaints across groups
                    complaint_bonus = min(user.complaints_count * 5, 30)
                    score += complaint_bonus
                    logger.debug(f"[Identity Tracking] User {user.username} has {user.complaints_count} total complaints. Complaint Bonus: +{complaint_bonus}")

        # Determine category based on thresholds (Module 5 Thresholds)
        category = "COLD"
        if score > 70:
            category = "HOT"
        elif score >= 40:
            category = "WARM"
            
        logger.info(f"[SLIE Predictive Engine] Buyer score for user {user_uuid}: {score} ({category} lead)")
        return score

    async def calculate_lead_score(self, lead_id: str, message_text: str, ai_result: dict) -> tuple[int, str]:
        """
        Calculates the lead score and determines strength using SLIE Elite formula (Module 7):
        score = intent_score + urgency_bonus + question_bonus
        """
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if not lead:
                return 0, "ignore"
            
            # 1. Intent Score (from AI Module 6)
            intent_score = ai_result.get("intent_score", 0)
            
            # 2. Urgency Bonus (2 if urgent phrases detected)
            has_urgency = any(kw in message_text.lower() for kw in URGENCY_KEYWORDS)
            urgency_bonus = 2 if has_urgency else 0
            
            # 3. Question Bonus (1 if question detected)
            question_bonus = 1 if "?" in message_text else 0
            
            # 4. Predictive Buyer Engine Integration (Module 5)
            buyer_score = await self.calculate_predictive_buyer_score(lead.user_id, message_text)
            
            # Total Formula (Module 7 spec)
            total_score = intent_score + urgency_bonus + question_bonus
            
            # Final classification based on combined signals
            strength = "ignore"
            if total_score >= 8 or buyer_score > 70:
                strength = "strong lead"
            elif total_score >= 5 or buyer_score > 40:
                strength = "potential lead"
            
            # Update Lead record
            lead.lead_score = total_score
            lead.lead_strength = strength
            db.commit()
                
            logger.info(f"[SLIE Lead Engine] Lead {lead_id} scored {total_score} (Strength: {strength})")
            return total_score, strength
        
        # Strength rules (Module 7 spec)
        if total_score >= 8:
            strength = "high lead"
        elif total_score >= 5:
            strength = "medium lead"
        else:
            strength = "ignore"
            
        return total_score, strength

    async def create_lead(self, user_id: int, username: str, group_id: str, message_text: str, message_id: str = None):
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
                return None # Should have been created by scraper

            # Check if lead already exists but is still NEW
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
                    original_message=message_text,
                    timestamp=datetime.utcnow(),
                    conversion_stage=ConversionStage.NEW
                )
                db.add(lead)
                db.flush()

            # 2. OPPORTUNITY SCORING (Module 1)
            opp_score, priority = await opportunity_engine.score_lead(lead.id)
            
            # 3. LTV SCORING (Module 2)
            ltv_score, ltv_tier = ltv_engine.calculate_ltv_score(lead.id)

            # 4. Trigger Async Power Upgrades
            db.refresh(lead)
            asyncio.create_task(power_upgrades_service.detect_lead_temperature(lead.id, message_text))
            asyncio.create_task(opportunity_engine.process_lead_opportunity(lead.id)) # Keeps old logic for now if needed
            asyncio.create_task(memory_engine.generate_conversation_summary(lead.id))

            # Store initial history
            new_conv = LeadConversation(
                lead_id=lead.id,
                message=message_text,
                sender="User",
                timestamp=datetime.utcnow()
            )
            db.add(new_conv)
            db.commit()
            
            logger.info(f"[SLIE Lead Engine] Lead processed: {username} (Opp: {opp_score}/{priority}, LTV: {ltv_score}/{ltv_tier})")
            return lead
            
            # Store initial message in history
            db.refresh(new_lead)

            # Elite Module 2: Lead Temperature Detection (Async)
            asyncio.create_task(power_upgrades_service.detect_lead_temperature(new_lead.id, message_text))

            # Elite Module 14: Intent-Aware Influence & Opportunity Engine (Async)
            asyncio.create_task(opportunity_engine.process_lead_opportunity(new_lead.id))

            # Elite Module 15: Memory Engine - Generate Summary (Async)
            asyncio.create_task(memory_engine.generate_conversation_summary(new_lead.id))

            # Elite Module 16: LTV Engine - Calculate Score (Async)
            # Run after a short delay to ensure memory summary is ready
            async def run_ltv_delayed(lid):
                await asyncio.sleep(2)
                ltv_engine.calculate_ltv_score(lid)
            asyncio.create_task(run_ltv_delayed(new_lead.id))

            new_conv = LeadConversation(
                lead_id=new_lead.id,
                message=message_text,
                sender="User",
                timestamp=datetime.utcnow()
            )
            db.add(new_conv)
            db.commit()
            
            logger.info(f"New lead created and history started: {username} ({strength}, score: {score})")
            return new_lead

    async def get_top_leads(self, limit: int = 10) -> List[Lead]:
        """
        Retrieves the leads with the highest scores.
        """
        with SessionLocal() as db:
            result = db.execute(
                select(Lead)
                .order_by(desc(Lead.lead_score))
                .limit(limit)
            ).scalars().all()
            return list(result)

lead_scoring_engine = LeadScoringEngine()

# Exportable functions
async def calculate_lead_score(message: str):
    return await lead_scoring_engine.calculate_lead_score(message)

async def create_lead(user_id: int, username: str, group_id: str, message: str):
    return await lead_scoring_engine.create_lead(user_id, username, group_id, message)

async def get_top_leads(limit: int = 10):
    return await lead_scoring_engine.get_top_leads(limit)
