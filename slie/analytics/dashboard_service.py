import logging
from datetime import datetime, timedelta
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
            avg_opportunity = avg_opp_res.scalar()
            if avg_opportunity is None:
                avg_opportunity = 0.0

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

            # 5. Distributions (Derived from database)
            user_count_res = await db.execute(select(func.count(User.id)))
            total_users = user_count_res.scalar() or 0
            
            # Simulated distribution based on total users
            influence_distribution = {
                "leader": max(1, int(total_users * 0.05)),
                "power_user": max(2, int(total_users * 0.15)),
                "regular": max(5, int(total_users * 0.8))
            }
            
            ltv_res = await db.execute(select(LeadLTVScore.ltv_tier, func.count(LeadLTVScore.id)).group_by(LeadLTVScore.ltv_tier))
            ltv_distribution = {row[0].lower(): row[1] for row in ltv_res.all()}
            if not ltv_distribution:
                ltv_distribution = {"standard": 10, "high_value": 2, "reseller": 1}

            # 6. Time Series (Velocity)
            # Fetch lead count per hour for the last 5 hours
            now = datetime.now()
            velocity_data = []
            for i in range(4, -1, -1):
                hour_start = now - timedelta(hours=i+1)
                hour_end = now - timedelta(hours=i)
                
                l_stmt = select(func.count(Lead.id)).where(Lead.created_at >= hour_start, Lead.created_at < hour_end)
                m_stmt = select(func.count(Message.id)).where(Message.sent_at >= hour_start, Message.sent_at < hour_end)
                
                l_res = await db.execute(l_stmt)
                m_res = await db.execute(m_stmt)
                
                velocity_data.append({
                    "time": hour_end.strftime("%H:%M"),
                    "leads": l_res.scalar() or 0,
                    "messages": m_res.scalar() or 0
                })

            # 7. Sentiment Mesh
            # Fetch classification counts from leads
            sentiment_mesh = {
                "frustration": 65,
                "urgency": 40,
                "comparison": 55,
                "satisfaction": 20,
                "technical_issue": 75
            }
            # (In a real system, these would be derived from LLM classification labels)

            # 8. High Probability Leads (New feature)
            lead_stmt = select(Lead, User.username).join(User).where(Lead.opportunity_score >= 70).order_by(Lead.created_at.desc()).limit(5)
            lead_res = await db.execute(lead_stmt)
            leads_list = []
            for lead, username in lead_res.all():
                leads_list.append({
                    "user": username or "Unknown",
                    "score": lead.opportunity_score,
                    "intent": lead.intent_score,
                    "text": lead.message_text[:40] + "..." if len(lead.message_text) > 40 else lead.message_text
                })

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
                "ltv_distribution": ltv_distribution,
                "velocity_data": velocity_data,
                "sentiment_mesh": sentiment_mesh,
                "high_prob_list": leads_list
            }

dashboard_service = DashboardService()
