import logging
from sqlalchemy import select
from slie.core.database import AsyncSessionLocal
from slie.models.lead_models import User, LeadLTVScore, Lead

logger = logging.getLogger(__name__)

class LTVScoringEngine:
    """
    STEP 10: LEAD LIFETIME VALUE ENGINE
    Estimate long-term value of a lead and detect reseller potential.
    """
    RESELLER_KEYWORDS = [
        "xtream codes", "panel access", "reseller credits", "server management",
        "billing system", "api integration", "bulk accounts", "whitelist dns"
    ]

    async def calculate_ltv(self, user_id: str) -> float:
        """
        ltv_score = (technical_keywords * 0.4) + (group_influence * 0.3) + (activity_frequency * 0.3)
        """
        async with AsyncSessionLocal() as db:
            # 1. Fetch User and their messages
            user_stmt = select(User).where(User.id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if not user:
                return 0.0

            # 2. Compute technical_keywords score
            # Fetch user messages to detect keywords
            # For simplicity, we use the user's technical_questions_count and keywords in leads
            tech_score = min(user.technical_questions_count * 20, 100.0)
            
            # 3. Compute group_influence (how many groups have we seen this user in?)
            group_influence = min(user.groups_seen * 25, 100.0)
            
            # 4. Compute activity_frequency
            activity_frequency = min(user.message_frequency * 5, 100.0)
            
            # 5. Formula calculation
            ltv_score = (tech_score * 0.4) + (group_influence * 0.3) + (activity_frequency * 0.3)
            
            # 6. Classification
            if ltv_score > 80:
                ltv_tier = "RESELLER_POTENTIAL"
            elif 50 <= ltv_score <= 80:
                ltv_tier = "HIGH_VALUE_BUYER"
            else:
                ltv_tier = "STANDARD_BUYER"
            
            # 7. Store result
            ltv_stmt = select(LeadLTVScore).where(LeadLTVScore.user_id == user.id)
            ltv_result = await db.execute(ltv_stmt)
            ltv_record = ltv_result.scalar_one_or_none()
            
            if ltv_record:
                ltv_record.ltv_score = ltv_score
                ltv_record.ltv_tier = ltv_tier
            else:
                new_ltv = LeadLTVScore(
                    user_id=user.id,
                    ltv_score=ltv_score,
                    ltv_tier=ltv_tier
                )
                db.add(new_ltv)
            
            await db.commit()
            
            # Logging (Requirement)
            if ltv_tier in ["RESELLER_POTENTIAL", "HIGH_VALUE_BUYER"]:
                logger.info(f"[SLIE Lead Engine] high value lead detected: {user.username} - LTV: {ltv_score:.2f} ({ltv_tier})")
            
            return ltv_score

ltv_engine = LTVScoringEngine()
