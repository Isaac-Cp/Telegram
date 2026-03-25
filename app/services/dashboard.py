from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.consent import Consent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.follow_up_job import FollowUpJob
from app.models.message import Message
from app.models.ticket import Ticket
from app.models.group import Group
from app.models.lead import Lead
from app.models.enums import ConversationStatus, FollowUpJobStatus, MessageDirection, TicketStatus, ConversionStage
from app.schemas.dashboard import DashboardSummary, LeadStats, GroupPerformance, DailyTrend, ConversionFunnel


from app.models.external_lead import ExternalLead
from sqlalchemy import desc, and_, case
import logging

from app.models.lead_opportunity import LeadOpportunity
from app.models.conversation_memory import LeadValueScore
from app.intelligence.models.influence_models import InfluenceProfile
from app.intelligence.models.competitor_models import CompetitorInsight
from app.intelligence.models.conversion_models import ConversionPrediction

logger = logging.getLogger(__name__)

def get_stats(db: Session):
    """
    Elite Module 12: Performance Tracking Metrics.
    Enhanced with Ultimate Intelligence Layer.
    """
    # 1. total groups joined
    total_groups_joined = db.query(func.count(Group.id)).filter(Group.joined == True).scalar() or 0
    
    # 2. messages analyzed
    messages_analyzed = db.query(func.count(Message.id)).scalar() or 0
    
    # 3. leads detected
    leads_detected = db.query(func.count(Lead.id)).scalar() or 0
    
    # 4. DMs sent
    dms_sent = db.query(func.count(Lead.id)).filter(Lead.dm_sent == True).scalar() or 0
    
    # 5. conversion rate
    conversions = db.query(func.count(Lead.id)).filter(Lead.conversion_stage == ConversionStage.CONVERTED).scalar() or 0
    conversion_rate = (conversions / leads_detected * 100) if leads_detected > 0 else 0
    
    # 6. Ultimate Intelligence Layer Metrics
    # Influence Distribution
    influence_distribution = {
        "leader": db.query(func.count(InfluenceProfile.id)).filter(InfluenceProfile.influence_level == "community_leader").scalar() or 0,
        "power_user": db.query(func.count(InfluenceProfile.id)).filter(InfluenceProfile.influence_level == "power_user").scalar() or 0,
        "regular": db.query(func.count(InfluenceProfile.id)).filter(InfluenceProfile.influence_level == "regular_member").scalar() or 0
    }

    # Competitor Insights
    top_competitors = db.query(CompetitorInsight).order_by(desc(CompetitorInsight.weakness_score)).limit(5).all()
    competitor_stats = [
        {
            "name": c.competitor_name,
            "score": round(c.weakness_score, 2),
            "complaints": c.complaint_count
        } for c in top_competitors
    ]

    # Conversion Probabilities
    high_prob_leads = db.query(func.count(ConversionPrediction.id)).filter(ConversionPrediction.conversion_tier == "high_conversion_probability").scalar() or 0
    
    # LTV Metrics (Updated)
    ltv_stats = db.query(
        LeadValueScore.ltv_tier,
        func.count(LeadValueScore.id).label("count")
    ).group_by(LeadValueScore.ltv_tier).all()
    
    ltv_distribution = {row.ltv_tier: row.count for row in ltv_stats}

    # Account Health (Human Engine)
    from app.models.telegram_account import TelegramAccount
    accounts = db.query(TelegramAccount).all()
    account_health = [
        {
            "phone": a.phone_number,
            "status": a.status,
            "replies_left": 5 - a.daily_reply_count, # Based on SAFE_DAILY_LIMITS
            "dms_left": 10 - a.daily_dm_count,
            "joins_left": 2 - a.groups_joined
        } for a in accounts
    ]

    # Live Activity Log (Latest 10 interactions)
    from app.models.conversation_memory import UnifiedConversation
    recent_activity = db.query(UnifiedConversation).order_by(desc(UnifiedConversation.timestamp)).limit(10).all()
    activity_log = [
        {
            "user": a.user.username if a.user else "Unknown",
            "type": a.message_type,
            "text": a.message_text[:50] + "..." if len(a.message_text) > 50 else a.message_text,
            "time": a.timestamp.strftime("%H:%M:%S")
        } for a in recent_activity
    ]

    return {
        "total_groups_joined": total_groups_joined,
        "messages_analyzed": messages_analyzed,
        "leads_detected": leads_detected,
        "conversions": conversions,
        "conversion_rate": round(conversion_rate, 2),
        "high_prob_leads": high_prob_leads,
        "influence_distribution": influence_distribution,
        "competitor_stats": competitor_stats,
        "ltv_distribution": ltv_distribution,
        "account_health": account_health,
        "activity_log": activity_log,
        "dms_sent": dms_sent
    }


def get_conversions_elite(db: Session):
    """Elite Module 12 Conversions List"""
    converted_leads = db.query(Lead).filter(Lead.conversion_stage == ConversionStage.CONVERTED).all()
    return [{
        "username": l.username,
        "temperature": l.lead_temperature,
        "last_contact": l.last_contact,
        "score": l.lead_score
    } for l in converted_leads]

def get_reseller_prospects_elite(db: Session):
    """Elite Module 16: Get Top Reseller Prospects"""
    prospects = db.query(Lead, LeadValueScore)\
        .join(LeadValueScore, LeadValueScore.user_id == Lead.id)\
        .filter(LeadValueScore.ltv_level == "high value reseller prospect")\
        .order_by(desc(LeadValueScore.ltv_score))\
        .limit(10).all()
    
    return [{
        "username": l.username,
        "score": s.ltv_score,
        "level": s.ltv_level,
        "last_updated": s.last_updated
    } for l, s in prospects]

def get_leads_elite(db: Session):
    """Module 16 Elite Leads List"""
    leads = db.query(Lead).order_by(desc(Lead.lead_score)).limit(50).all()
    return [{
        "username": l.username,
        "score": l.lead_score,
        "temperature": l.lead_temperature,
        "status": l.conversion_stage.value,
        "last_contact": l.last_contact
    } for l in leads]

def get_groups_elite(db: Session):
    """Elite Module 12 & 14 Groups List"""
    groups = db.query(Group).filter(Group.joined == True).order_by(desc(Group.authority_score)).all()
    return [{
        "name": g.name,
        "members": g.members_count,
        "score": g.authority_score,
        "density": round(g.seller_density, 2),
        "status": g.saturation_status
    } for g in groups]

def get_conversations_elite(db: Session):
    """Module 16 Elite Conversations History"""
    from app.models.lead_conversation import LeadConversation
    convs = db.query(LeadConversation).order_by(desc(LeadConversation.timestamp)).limit(50).all()
    return [{
        "lead_id": c.lead_id,
        "sender": c.sender,
        "message": c.message,
        "timestamp": c.timestamp
    } for c in convs]

def get_dashboard_summary(db: Session) -> DashboardSummary:
    today = date.today()

    # ... existing logic for messages ...
    inbound_messages_today = (
        db.query(func.count(Message.id))
        .filter(
            Message.direction == MessageDirection.INBOUND,
            func.date(Message.sent_at) == today,
        )
        .scalar()
        or 0
    )

    outbound_messages_today = (
        db.query(func.count(Message.id))
        .filter(
            Message.direction == MessageDirection.OUTBOUND,
            func.date(Message.sent_at) == today,
        )
        .scalar()
        or 0
    )

    # SLIE Metrics
    groups_joined = db.query(func.count(Group.id)).filter(Group.joined == True).scalar() or 0
    leads_detected_total = db.query(func.count(Lead.id)).scalar() or 0
    leads_detected_today = db.query(func.count(Lead.id)).filter(func.date(Lead.created_at) == today).scalar() or 0
    public_replies_sent = db.query(func.count(Lead.id)).filter(Lead.public_reply_sent == True).scalar() or 0
    dms_sent = db.query(func.count(Lead.id)).filter(Lead.dm_sent == True).scalar() or 0
    
    # Calculate rates
    replies_received = db.query(func.count(Lead.id)).filter(Lead.conversion_stage != ConversionStage.CONTACTED, Lead.dm_sent == True).scalar() or 0
    reply_rate = (replies_received / dms_sent * 100) if dms_sent > 0 else 0.0
    
    conversions = db.query(func.count(Lead.id)).filter(Lead.conversion_stage == ConversionStage.CONVERTED).scalar() or 0
    conversion_rate = (conversions / leads_detected_total * 100) if leads_detected_total > 0 else 0.0

    # Detailed Data
    recent_leads_query = db.query(Lead).join(Group, Lead.group_id == Group.id, isouter=True).order_by(Lead.created_at.desc()).limit(10).all()
    recent_leads = [
        LeadStats(
            username=l.username,
            lead_score=l.lead_score,
            lead_strength=l.lead_strength,
            status=l.conversion_stage.value,
            group_name=l.group.name if l.group else "Direct/Unknown",
            last_contact=l.last_contact
        ) for l in recent_leads_query
    ]

    top_groups_query = db.query(
        Group.name,
        Group.authority_score,
        Group.messages_last_24h,
        func.count(Lead.id).label("leads_count")
    ).join(Lead, Lead.group_id == Group.id, isouter=True)\
     .group_by(Group.id, Group.name, Group.authority_score, Group.messages_last_24h)\
     .order_by(desc(Group.authority_score)).limit(5).all()
    
    top_groups = [
        GroupPerformance(
            group_name=g.name,
            leads_generated=g.leads_count,
            messages_scanned=g.messages_last_24h or 0
        ) for g in top_groups_query
    ]

    # Daily Trend (last 7 days)
    seven_days_ago = today - timedelta(days=7)
    daily_trend_query = db.query(
        func.date(Lead.created_at).label("date"),
        func.count(Lead.id).label("count")
    ).filter(Lead.created_at >= seven_days_ago)\
     .group_by(func.date(Lead.created_at)).order_by("date").all()
    
    daily_trend = [DailyTrend(date=str(row.date), count=row.count) for row in daily_trend_query]

    # Conversion Funnel
    funnel_data = db.query(
        Lead.conversion_stage,
        func.count(Lead.id).label("count")
    ).group_by(Lead.conversion_stage).all()
    
    conversion_funnel = [ConversionFunnel(stage=row.conversion_stage.value, count=row.count) for row in funnel_data]

    # Elite Upgrade Stats
    elite_stats = get_stats(db)

    return DashboardSummary(
        contacts_total=db.query(func.count(Contact.id)).scalar() or 0,
        active_consents=db.query(func.count(Consent.id)).filter(Consent.revoked_at.is_(None)).scalar() or 0,
        open_conversations=(
            db.query(func.count(Conversation.id))
            .filter(Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]))
            .scalar()
            or 0
        ),
        open_tickets=(
            db.query(func.count(Ticket.id))
            .filter(Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]))
            .scalar()
            or 0
        ),
        follow_ups_due=(
            db.query(func.count(FollowUpJob.id))
            .filter(FollowUpJobStatus.QUEUED == FollowUpJobStatus.QUEUED) # Fixed typo
            .scalar()
            or 0
        ),
        inbound_messages_today=inbound_messages_today,
        outbound_messages_today=outbound_messages_today,
        groups_joined=groups_joined,
        leads_detected_total=leads_detected_total,
        leads_detected_today=leads_detected_today,
        public_replies_sent=public_replies_sent,
        dms_sent=dms_sent,
        reply_rate=reply_rate,
        conversion_rate=conversion_rate,
        high_value_leads=elite_stats["high_value_leads"],
        reseller_prospects=elite_stats["reseller_prospects"],
        average_ltv_score=elite_stats["average_ltv_score"],
        ltv_distribution=elite_stats["ltv_distribution"],
        problem_distribution=elite_stats["problem_distribution"],
        persona_performance=elite_stats["persona_performance"],
        account_health=elite_stats["account_health"],
        recent_leads=recent_leads,
        top_groups=top_groups,
        daily_trend=daily_trend,
        conversion_funnel=conversion_funnel
    )

