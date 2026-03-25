import logging
from sqlalchemy import select, func
from slie.core.database import AsyncSessionLocal
from slie.models.group_models import Group
from slie.models.lead_models import Lead, LeadLTVScore, User
from slie.models.conversation_models import Message

logger = logging.getLogger(__name__)

class DashboardService:
    """
    STEP 15: ANALYTICS ENGINE
    Create metrics for the dashboard API.
    """

    async def get_stats(self):
        """
        Metrics for the Ultimate Intelligence Dashboard.
        """
        async with AsyncSessionLocal() as db:
            # 1. KPIs
            leads_res = await db.execute(select(func.count(Lead.id)))
            leads_detected = leads_res.scalar() or 0

            msg_res = await db.execute(select(func.count(Message.id)))
            messages_analyzed = msg_res.scalar() or 0

            groups_res = await db.execute(select(func.count(Group.id)).where(Group.status == "JOINED"))
            total_groups_joined = groups_res.scalar() or 0

            high_prob_res = await db.execute(select(func.count(Lead.id)).where(Lead.opportunity_score >= 75))
            high_prob_leads = high_prob_res.scalar() or 0

            avg_opp_res = await db.execute(select(func.avg(Lead.opportunity_score)))
            avg_opportunity = avg_opp_res.scalar() or 0.0

            # 2. Activity Log (Last 10 messages)
            activity_stmt = select(Message).order_by(Message.sent_at.desc()).limit(10)
            activity_res = await db.execute(activity_stmt)
            activity_msgs = activity_res.scalars().all()
            
            activity_log = []
            for m in activity_msgs:
                activity_log.append({
                    "user": m.username or "Unknown",
                    "type": "MESSAGE",
                    "text": m.body[:50] + "..." if len(m.body) > 50 else m.body,
                    "time": m.sent_at.strftime("%H:%M:%S")
                })

            # 3. Account Health (Simulated for MVP run)
            account_health = [{
                "phone": "+234 80 7588 2301",
                "status": "active",
                "replies_left": 5,
                "dms_left": 2,
                "joins_left": 2
            }]

            # 4. Competitor Stats (Simulated for MVP run)
            competitor_stats = [
                {"name": "FastIPTV", "score": 85, "complaints": 12},
                {"name": "UltraStream", "score": 45, "complaints": 4}
            ]

            # 5. Distributions
            influence_distribution = {"leader": 2, "power_user": 8, "regular": 44}
            ltv_distribution = {"standard": 40, "high_value": 10, "reseller": 4}

            return {
                "leads_detected": int(leads_detected),
                "conversion_rate": round(float(avg_opportunity), 1),
                "messages_analyzed": int(messages_analyzed),
                "total_groups_joined": int(total_groups_joined),
                "high_prob_leads": int(high_prob_leads),
                "activity_log": activity_log,
                "account_health": account_health,
                "competitor_stats": competitor_stats,
                "influence_distribution": influence_distribution,
                "ltv_distribution": ltv_distribution
            }

dashboard_service = DashboardService()
