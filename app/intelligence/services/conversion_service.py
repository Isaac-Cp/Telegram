import logging
from datetime import datetime
from sqlalchemy import select, and_
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.lead_opportunity import LeadOpportunity
from app.models.conversation_memory import LeadValueScore
from app.intelligence.models.influence_models import InfluenceProfile
from app.intelligence.models.conversion_models import ConversionPrediction

logger = logging.getLogger(__name__)

class ConversionProbabilityEngine:
    """
    MODULE 3 - CONVERSION PROBABILITY ENGINE
    Predict the probability that a detected lead will convert.
    """

    def calculate_conversion_probability(self, lead_id: str):
        """
        STEP 1, 2 & 3: Normalize features and compute conversion_probability.
        """
        with SessionLocal() as db:
            lead = db.get(Lead, lead_id)
            if not lead:
                logger.warning(f"[SLIE Conversion Engine] Lead {lead_id} not found.")
                return None

            # 1. Fetch input features from existing engines
            opportunity = db.execute(
                select(LeadOpportunity).where(LeadOpportunity.lead_id == lead.id)
            ).scalar_one_or_none()
            
            ltv = db.execute(
                select(LeadValueScore).where(LeadValueScore.user_id == lead.user_id)
            ).scalar_one_or_none()
            
            influence = db.execute(
                select(InfluenceProfile).where(
                    and_(
                        InfluenceProfile.user_id == lead.user_id,
                        InfluenceProfile.group_id == lead.group_id
                    )
                )
            ).scalar_one_or_none()

            # 2. FEATURE NORMALIZATION (Values 0 to 1)
            opp_score_norm = (opportunity.opportunity_score / 10.0) if opportunity else 0.0
            ltv_score_norm = (ltv.ltv_score / 10.0) if ltv else 0.0
            influence_score_norm = (influence.influence_score / 100.0) if influence else 0.0
            
            # Engagement Score based on message count (Module 1 Influence Engine reuses this)
            engagement_count = db.query(Lead.original_message).count() # Simplified placeholder
            engagement_score_norm = min(1.0, engagement_count / 10.0) # 10+ messages for full engagement score

            # 3. CONVERSION MODEL calculation
            # conversion_probability = (opportunity_score * 0.4) + (ltv_score * 0.3) + (influence_score * 0.2) + (engagement_score * 0.1)
            # Normalizing to 0-100% scale
            probability = (opp_score_norm * 40) + (ltv_score_norm * 30) + (influence_score_norm * 20) + (engagement_score_norm * 10)
            probability = round(max(0.0, min(100.0, probability)), 2)

            # STEP 4: PROBABILITY CLASSIFICATION
            if probability > 75:
                tier = "high_conversion_probability"
            elif probability > 50:
                tier = "medium_conversion_probability"
            else:
                tier = "low_conversion_probability"

            # STEP 5: DATABASE UPDATE
            prediction = db.execute(
                select(ConversionPrediction).where(ConversionPrediction.lead_id == lead_id)
            ).scalar_one_or_none()

            if not prediction:
                prediction = ConversionPrediction(lead_id=lead_id)
                db.add(prediction)

            prediction.conversion_probability = probability
            prediction.conversion_tier = tier
            prediction.opportunity_score_norm = opp_score_norm
            prediction.ltv_score_norm = ltv_score_norm
            prediction.influence_score_norm = influence_score_norm
            prediction.engagement_score_norm = engagement_score_norm
            prediction.last_updated = datetime.utcnow()

            db.commit()
            
            # STEP 7: LOGGING
            if tier == "high_conversion_probability":
                logger.info(f"[SLIE Conversion Engine] high probability lead detected: {lead_id} - {probability}% ({tier})")
            else:
                logger.info(f"[SLIE Conversion Engine] conversion probability updated: {lead_id} - {probability}% ({tier})")
            
            return prediction

conversion_engine = ConversionProbabilityEngine()
