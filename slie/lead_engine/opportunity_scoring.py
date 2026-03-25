import logging
from sqlalchemy import select, update
from slie.core.database import AsyncSessionLocal
from slie.models.lead_models import Lead, LeadOpportunityScore, User

logger = logging.getLogger(__name__)

class OpportunityScoringEngine:
    """
    STEP 9: LEAD OPPORTUNITY SCORING ENGINE
    Calculate opportunity score using weighted formula.
    """

    async def calculate_score(self, lead_id: str) -> float:
        """
        opportunity_score = (intent_score * 0.5) + (urgency_score * 0.3) + (activity_score * 0.2)
        """
        async with AsyncSessionLocal() as db:
            # 1. Fetch Lead and User data
            stmt = select(Lead).where(Lead.id == lead_id)
            result = await db.execute(stmt)
            lead = result.scalar_one_or_none()
            if not lead:
                return 0.0

            user_stmt = select(User).where(User.id == lead.user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                activity_score = 0.0
            else:
                # activity_score based on messages_today (capped at 100)
                activity_score = min(user.messages_today * 10, 100.0)

            # 2. Formula calculation
            intent_score = lead.intent_score or 0.0
            urgency_score = lead.urgency_score or 0.0
            
            opportunity_score = (intent_score * 0.5) + (urgency_score * 0.3) + (activity_score * 0.2)
            
            # 3. Classification
            if opportunity_score > 75:
                priority = "HIGH_PRIORITY"
            elif 50 <= opportunity_score <= 75:
                priority = "MEDIUM_PRIORITY"
            else:
                priority = "LOW_PRIORITY"

            # 4. Store result
            lead.opportunity_score = opportunity_score
            lead.priority_level = priority
            
            # Update or create LeadOpportunityScore record
            score_stmt = select(LeadOpportunityScore).where(LeadOpportunityScore.lead_id == lead.id)
            score_result = await db.execute(score_stmt)
            score_record = score_result.scalar_one_or_none()
            
            if score_record:
                score_record.intent_score = intent_score
                score_record.urgency_score = urgency_score
                score_record.activity_score = activity_score
                score_record.opportunity_score = opportunity_score
                score_record.priority_level = priority
            else:
                new_score = LeadOpportunityScore(
                    lead_id=lead.id,
                    intent_score=intent_score,
                    urgency_score=urgency_score,
                    activity_score=activity_score,
                    opportunity_score=opportunity_score,
                    priority_level=priority
                )
                db.add(new_score)
            
            await db.commit()
            
            # Logging (Requirement)
            if priority == "HIGH_PRIORITY":
                logger.info(f"[SLIE Lead Engine] high priority lead detected: {lead.id} - Score: {opportunity_score:.2f}")
            
            return opportunity_score

opportunity_engine = OpportunityScoringEngine()
