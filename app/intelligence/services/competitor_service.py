import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import select, func, and_
from app.db.session import SessionLocal
from app.intelligence.models.competitor_models import CompetitorInsight
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class CompetitorScanner:
    """
    MODULE 2 - COMPETITOR WEAKNESS SCANNER
    Identify weaknesses in competing IPTV services based on user discussions.
    """

    async def analyze_message_for_competitors(self, message_text: str):
        """
        STEP 2 & 3: Extract competitor names and detect complaint categories.
        """
        prompt = f"""
        Analyze the following message for IPTV competitor mentions and complaints.
        Extract the competitor name and categorize the complaint.

        COMPLAINT CATEGORIES: buffering, server_down, channel_missing, poor_quality, price_complaints.

        MESSAGE: {message_text}

        Return JSON format:
        {{
            "competitor_name": "Name of competitor or null",
            "complaint_type": "one of the categories or null"
        }}
        """
        try:
            content = await ai_service.chat_completion(prompt=prompt, response_format="json_object")
            data = json.loads(content) if content else {}
            
            competitor_name = data.get("competitor_name")
            complaint_type = data.get("complaint_type")

            if competitor_name and complaint_type:
                await self.record_competitor_complaint(competitor_name, complaint_type)
        except Exception as e:
            logger.error(f"[SLIE Competitor Scanner] Error analyzing message: {e}")

    async def record_competitor_complaint(self, competitor_name: str, complaint_type: str):
        """
        STEP 4 & 5: Aggregate complaints and update weakness_score.
        """
        with SessionLocal() as db:
            competitor_name = competitor_name.strip().lower()
            
            insight = db.execute(
                select(CompetitorInsight).where(CompetitorInsight.competitor_name == competitor_name)
            ).scalar_one_or_none()

            if not insight:
                insight = CompetitorInsight(competitor_name=competitor_name, complaint_types={})
                db.add(insight)

            # Update complaint types JSON
            types = insight.complaint_types or {}
            types[complaint_type] = types.get(complaint_type, 0) + 1
            insight.complaint_types = types
            
            # Increment complaint count
            insight.complaint_count += 1
            
            # STEP 5: WEAKNESS SCORE calculation
            # Simplified formula for now
            # (complaint_count * 0.5) + (unique_users_reporting * 0.3) + (complaint_frequency * 0.2)
            # unique_users_reporting is placeholder for now, incrementing it with count
            insight.unique_users_reporting += 1
            
            # complaint_frequency (complaints per day since first recorded)
            days_since = (datetime.utcnow() - insight.created_at).days or 1
            insight.complaint_frequency = insight.complaint_count / days_since
            
            insight.weakness_score = (insight.complaint_count * 0.5) + (insight.unique_users_reporting * 0.3) + (insight.complaint_frequency * 0.2)
            insight.last_updated = datetime.utcnow()

            db.commit()
            logger.info(f"[SLIE Competitor Scanner] competitor weakness detected for {competitor_name}: {complaint_type} (Score: {insight.weakness_score:.2f})")

    def get_high_weakness_competitors(self, threshold: float = 10.0) -> List[CompetitorInsight]:
        """
        STEP 7: Flag competitors with high complaint levels.
        """
        with SessionLocal() as db:
            results = db.execute(
                select(CompetitorInsight)
                .where(CompetitorInsight.weakness_score >= threshold)
                .order_by(CompetitorInsight.weakness_score.desc())
            ).scalars().all()
            return list(results)

competitor_scanner = CompetitorScanner()
