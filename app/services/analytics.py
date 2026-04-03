import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, and_, desc, case
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.group import Group
from app.models.enums import ConversionStage

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    def get_daily_report(self) -> dict[str, Any]:
        """Generates a summary of the last 24 hours of activity."""
        today = datetime.utcnow().date()
        
        with SessionLocal() as db:
            leads_today = db.query(func.count(Lead.id)).filter(func.date(Lead.created_at) == today).scalar() or 0
            dms_sent_today = db.query(func.count(Lead.id)).filter(
                and_(Lead.dm_sent == True, func.date(Lead.last_contact) == today)
            ).scalar() or 0
            
            replies_today = db.query(func.count(Lead.id)).filter(
                and_(
                    Lead.conversion_stage.in_([ConversionStage.RESPONDED, ConversionStage.INTERESTED, ConversionStage.CONVERTED]),
                    func.date(Lead.last_contact) == today
                )
            ).scalar() or 0
            
            conversions_today = db.query(func.count(Lead.id)).filter(
                and_(Lead.conversion_stage == ConversionStage.CONVERTED, func.date(Lead.last_contact) == today)
            ).scalar() or 0
            
            reply_rate = (replies_today / dms_sent_today * 100) if dms_sent_today > 0 else 0.0
            conversion_rate = (conversions_today / leads_today * 100) if leads_today > 0 else 0.0
            
            return {
                "date": today.isoformat(),
                "leads_detected": leads_today,
                "dms_sent": dms_sent_today,
                "replies_received": replies_today,
                "conversions": conversions_today,
                "reply_rate": round(float(reply_rate), 2),
                "conversion_rate": round(float(conversion_rate), 2)
            }

    def get_weekly_report(self) -> dict[str, Any]:
        """Generates a summary of the last 7 days of activity."""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        with SessionLocal() as db:
            leads_total = db.query(func.count(Lead.id)).filter(Lead.created_at >= seven_days_ago).scalar() or 0
            dms_sent_total = db.query(func.count(Lead.id)).filter(
                and_(Lead.dm_sent == True, Lead.last_contact >= seven_days_ago)
            ).scalar() or 0
            
            replies_total = db.query(func.count(Lead.id)).filter(
                and_(
                    Lead.conversion_stage.in_([ConversionStage.RESPONDED, ConversionStage.INTERESTED, ConversionStage.CONVERTED]),
                    Lead.last_contact >= seven_days_ago
                )
            ).scalar() or 0
            
            conversions_total = db.query(func.count(Lead.id)).filter(
                and_(Lead.conversion_stage == ConversionStage.CONVERTED, Lead.last_contact >= seven_days_ago)
            ).scalar() or 0
            
            reply_rate = (replies_total / dms_sent_total * 100) if dms_sent_total > 0 else 0.0
            conversion_rate = (conversions_total / leads_total * 100) if leads_total > 0 else 0.0
            
            return {
                "period": "Last 7 Days",
                "leads_detected": leads_total,
                "dms_sent": dms_sent_total,
                "replies_received": replies_total,
                "conversions": conversions_total,
                "reply_rate": round(float(reply_rate), 2),
                "conversion_rate": round(float(conversion_rate), 2)
            }

    def get_group_performance_report(self, limit: int = 10) -> list[dict[str, Any]]:
        """Identifies the best performing groups based on lead quality and conversion."""
        with SessionLocal() as db:
            # Join Lead and Group to aggregate metrics per group
            results = db.query(
                Group.name,
                func.count(Lead.id).label("total_leads"),
                func.sum(case((Lead.conversion_stage == ConversionStage.CONVERTED, 1), else_=0)).label("conversions"),
                func.avg(Lead.lead_score).label("avg_score")
            ).join(Lead, Lead.group_id == Group.id)\
             .group_by(Group.id, Group.name)\
             .order_by(desc("conversions"), desc("avg_score"))\
             .limit(limit)\
             .all()
            
            performance = []
            for row in results:
                performance.append({
                    "group_name": row.name,
                    "total_leads": row.total_leads,
                    "conversions": int(row.conversions or 0),
                    "avg_lead_score": round(float(row.avg_score or 0.0), 2)
                })
            return performance

analytics_engine = AnalyticsEngine()

