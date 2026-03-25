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
        Metrics:
        - groups discovered
        - groups joined
        - leads detected
        - high-value leads
        - conversion probability (simulated for MVP)
        """
        async with AsyncSessionLocal() as db:
            # 1. Groups Discovered
            discovered_stmt = select(func.count(Group.id)).where(Group.status == "DISCOVERED")
            discovered_res = await db.execute(discovered_stmt)
            groups_discovered = discovered_res.scalar() or 0

            # 2. Groups Joined
            joined_stmt = select(func.count(Group.id)).where(Group.status == "JOINED")
            joined_res = await db.execute(joined_stmt)
            groups_joined = joined_res.scalar() or 0

            # 3. Leads Detected
            leads_stmt = select(func.count(Lead.id))
            leads_res = await db.execute(leads_stmt)
            leads_detected = leads_res.scalar() or 0

            # 4. High-Value Leads (LTV Tier = RESELLER_POTENTIAL or HIGH_VALUE_BUYER)
            hv_leads_stmt = select(func.count(LeadLTVScore.id)).where(
                LeadLTVScore.ltv_tier.in_(["RESELLER_POTENTIAL", "HIGH_VALUE_BUYER"])
            )
            hv_leads_res = await db.execute(hv_leads_stmt)
            high_value_leads = hv_leads_res.scalar() or 0

            # 5. Conversion Probability (Average Lead Opportunity Score)
            avg_opp_stmt = select(func.avg(Lead.opportunity_score))
            avg_opp_res = await db.execute(avg_opp_stmt)
            avg_opportunity = avg_opp_res.scalar() or 0.0

            # 6. Messages Analyzed
            msg_stmt = select(func.count(Message.id))
            msg_res = await db.execute(msg_stmt)
            messages_analyzed = msg_res.scalar() or 0

            return {
                "groups_discovered": groups_discovered,
                "groups_joined": groups_joined,
                "leads_detected": leads_detected,
                "high_value_leads": high_value_leads,
                "conversion_probability": round(float(avg_opportunity), 2),
                "messages_analyzed": messages_analyzed
            }

dashboard_service = DashboardService()
