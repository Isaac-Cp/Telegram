from datetime import datetime, timedelta, timezone

from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

import logging

from app.intelligence.models.competitor_models import CompetitorInsight
from app.intelligence.models.conversion_models import ConversionPrediction
from app.intelligence.models.influence_models import InfluenceProfile
from app.models.consent import Consent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_memory import ConversationSummary, LeadValueScore, UnifiedConversation
from app.models.enums import ConversationStatus, ConversionStage, FollowUpJobStatus, MessageDirection, TicketStatus
from app.models.follow_up_job import FollowUpJob
from app.models.group import Group
from app.models.lead import Lead
from app.models.message import Message
from app.models.message_analysis import MessageAnalysis
from app.models.ticket import Ticket
from app.schemas.dashboard import ConversionFunnel, DailyTrend, DashboardSummary, GroupPerformance, LeadStats

logger = logging.getLogger(__name__)

HIGH_VALUE_TIERS = {
    "high value buyer",
    "reseller potential",
    "high value reseller prospect",
}


def _build_account_health(db: Session) -> list[dict]:
    from app.models.telegram_account import TelegramAccount
    from app.services.proxy_manager import proxy_manager
    from app.services.human_engine import human_engine

    accounts = db.query(TelegramAccount).all()
    health_data = []
    active_cooldowns = human_engine.get_active_cooldowns()
    
    for account in accounts:
        proxy_config = proxy_manager.get_proxy_config(account)
        proxy_valid = proxy_manager.validate_proxy_connection(proxy_config) if proxy_config else True
        
        # Determine if this account is in cooldown (simplified)
        # In a multi-account setup, we'd need account-specific cooldown tracking
        # For now, we show the global bot cooldowns
        cooldown_until = None
        if active_cooldowns:
            cooldown_until = max(active_cooldowns.values())

        health_data.append({
            "phone": account.phone_number,
            "status": account.status,
            "dms_used": account.daily_dm_count,
            "replies_used": account.daily_reply_count,
            "joins_used": account.groups_joined,
            "dms_left": max(0, 10 - account.daily_dm_count),
            "replies_left": max(0, 5 - account.daily_reply_count),
            "joins_left": max(0, 2 - account.groups_joined),
            "proxy_status": proxy_valid,
            "cooldown_until": cooldown_until
        })
    return health_data


def get_stats(db: Session):
    """
    Elite Module 12: Performance Tracking Metrics.
    Enhanced with Ultimate Intelligence Layer.
    """
    total_groups_joined = db.query(func.count(Group.id)).filter(Group.joined.is_(True)).scalar() or 0
    messages_analyzed = db.query(func.count(Message.id)).scalar() or 0
    leads_detected = db.query(func.count(Lead.id)).scalar() or 0
    dms_sent = db.query(func.count(Lead.id)).filter(Lead.dm_sent.is_(True)).scalar() or 0

    conversions = db.query(func.count(Lead.id)).filter(Lead.conversion_stage == ConversionStage.CONVERTED).scalar() or 0
    conversion_rate = (conversions / leads_detected * 100) if leads_detected > 0 else 0

    influence_distribution = {
        "leader": db.query(func.count(InfluenceProfile.id)).filter(InfluenceProfile.influence_level == "community_leader").scalar() or 0,
        "power_user": db.query(func.count(InfluenceProfile.id)).filter(InfluenceProfile.influence_level == "power_user").scalar() or 0,
        "regular": db.query(func.count(InfluenceProfile.id)).filter(InfluenceProfile.influence_level == "regular_member").scalar() or 0,
    }

    top_competitors = db.query(CompetitorInsight).order_by(desc(CompetitorInsight.weakness_score)).limit(5).all()
    competitor_stats = [
        {
            "name": competitor.competitor_name,
            "score": round(competitor.weakness_score, 2),
            "complaints": competitor.complaint_count,
        }
        for competitor in top_competitors
    ]

    high_prob_leads = (
        db.query(func.count(ConversionPrediction.id))
        .filter(ConversionPrediction.conversion_tier == "high_conversion_probability")
        .scalar()
        or 0
    )

    ltv_stats = (
        db.query(
            LeadValueScore.ltv_tier,
            func.count(LeadValueScore.id).label("count"),
        )
        .group_by(LeadValueScore.ltv_tier)
        .all()
    )
    ltv_distribution = {row.ltv_tier: row.count for row in ltv_stats}
    average_ltv_score = db.query(func.avg(LeadValueScore.ltv_score)).scalar() or 0.0
    high_value_leads = (
        db.query(func.count(LeadValueScore.id))
        .filter(func.lower(LeadValueScore.ltv_tier).in_(HIGH_VALUE_TIERS))
        .scalar()
        or 0
    )
    reseller_prospects = (
        db.query(func.count(LeadValueScore.id))
        .filter(func.lower(LeadValueScore.ltv_tier).like("%reseller%"))
        .scalar()
        or 0
    )

    problem_rows = (
        db.query(
            ConversationSummary.problem_type,
            func.count(ConversationSummary.id).label("count"),
        )
        .filter(ConversationSummary.problem_type.is_not(None))
        .group_by(ConversationSummary.problem_type)
        .all()
    )
    problem_distribution = {row.problem_type: row.count for row in problem_rows if row.problem_type}

    # Sentiment Trends over time (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    sentiment_time_rows = db.query(
        func.date(Message.sent_at).label('date'),
        MessageAnalysis.problem_type,
        func.count(MessageAnalysis.id).label('count')
    ).join(Message, Message.id == MessageAnalysis.message_id)\
     .filter(Message.sent_at >= seven_days_ago)\
     .group_by('date', MessageAnalysis.problem_type).all()
    
    sentiment_trends = {}
    for row in sentiment_time_rows:
        d = str(row.date)
        if d not in sentiment_trends:
            sentiment_trends[d] = {}
        sentiment_trends[d][row.problem_type or "General"] = row.count

    # Hourly Heatmap (Lead detection hours)
    heatmap_rows = db.query(
        func.extract('hour', Lead.timestamp).label('hour'),
        func.count(Lead.id).label('count')
    ).group_by('hour').all()
    hourly_heatmap = [{"hour": int(row.hour), "count": row.count} for row in heatmap_rows]

    persona_name = func.coalesce(Lead.persona_id, "Unassigned")
    persona_rows = (
        db.query(
            persona_name.label("name"),
            func.count(Lead.id).label("leads"),
            func.sum(case((Lead.conversion_stage == ConversionStage.CONVERTED, 1), else_=0)).label("conversions"),
        )
        .group_by(persona_name)
        .order_by(desc("leads"))
        .all()
    )
    persona_performance = [
        {
            "name": row.name,
            "leads": row.leads,
            "conversions": row.conversions or 0,
            "rate": round(((row.conversions or 0) / row.leads) * 100, 2) if row.leads else 0.0,
        }
        for row in persona_rows
    ]

    recent_activity = db.query(UnifiedConversation).order_by(desc(UnifiedConversation.timestamp)).limit(10).all()
    activity_log = [
        {
            "user": activity.user.username if activity.user else "Unknown",
            "type": activity.message_type,
            "text": ((activity.message_text or "")[:50] + "...") if activity.message_text and len(activity.message_text) > 50 else (activity.message_text or ""),
            "time": activity.timestamp.strftime("%H:%M:%S"),
        }
        for activity in recent_activity
    ]

    return {
        "total_groups_joined": total_groups_joined,
        "messages_analyzed": messages_analyzed,
        "leads_detected": leads_detected,
        "conversions": conversions,
        "conversion_rate": round(conversion_rate, 2),
        "high_prob_leads": high_prob_leads,
        "high_value_leads": high_value_leads,
        "reseller_prospects": reseller_prospects,
        "average_ltv_score": round(float(average_ltv_score), 2),
        "influence_distribution": influence_distribution,
        "competitor_stats": competitor_stats,
        "ltv_distribution": ltv_distribution,
        "problem_distribution": problem_distribution,
        "sentiment_trends": sentiment_trends,
        "hourly_heatmap": hourly_heatmap,
        "persona_performance": persona_performance,
        "account_health": _build_account_health(db),
        "activity_log": activity_log,
        "dms_sent": dms_sent,
    }


def get_high_intent_buyers_elite(db: Session):
    """
    Elite Step: Returns the top 20 high-intent buyers detected in the last 7 days.
    Uses the Multi-Layer Dynamic Scoring model.
    """
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Query leads with score >= 60 (Warm/Hot) in last 7 days
    leads = (
        db.query(Lead)
        .filter(Lead.timestamp >= seven_days_ago)
        .filter(Lead.lead_score >= 60)
        .order_by(desc(Lead.lead_score))
        .limit(20)
        .all()
    )
    
    return [
        {
            "username": lead.user.username if lead.user else "Anonymous",
            "score": lead.lead_score,
            "intent": lead.intent_score,
            "problem": lead.urgency_score,
            "engagement": lead.engagement_score,
            "recency": lead.recency_score,
            "pattern": lead.pattern_score,
            "temperature": lead.lead_temperature,
            "timestamp": lead.timestamp.isoformat(),
            "message": lead.message_text[:100] + ("..." if len(lead.message_text) > 100 else "")
        }
        for lead in leads
    ]


def get_conversions_elite(db: Session):
    converted_leads = db.query(Lead).filter(Lead.conversion_stage == ConversionStage.CONVERTED).all()
    return [
        {
            "username": lead.user.username if lead.user else None,
            "temperature": lead.lead_temperature,
            "last_contact": lead.last_contact,
            "score": lead.lead_score,
        }
        for lead in converted_leads
    ]


def get_reseller_prospects_elite(db: Session):
    prospects = (
        db.query(Lead, LeadValueScore)
        .join(LeadValueScore, LeadValueScore.user_id == Lead.user_id)
        .filter(func.lower(LeadValueScore.ltv_tier).like("%reseller%"))
        .order_by(desc(LeadValueScore.ltv_score))
        .limit(10)
        .all()
    )

    return [
        {
            "username": lead.user.username if lead.user else None,
            "score": score.ltv_score,
            "level": score.ltv_tier,
            "last_updated": score.last_updated,
        }
        for lead, score in prospects
    ]


def get_leads_elite(db: Session):
    leads = db.query(Lead).order_by(desc(Lead.lead_score)).limit(50).all()
    return [
        {
            "username": lead.user.username if lead.user else None,
            "score": lead.lead_score,
            "temperature": lead.lead_temperature,
            "status": lead.conversion_stage.value,
            "last_contact": lead.last_contact,
        }
        for lead in leads
    ]


def get_groups_elite(db: Session):
    groups = db.query(Group).filter(Group.joined.is_(True)).order_by(desc(Group.authority_score)).all()
    return [
        {
            "name": group.name,
            "members": group.members_count,
            "score": group.authority_score,
            "density": round(group.seller_density, 2),
            "status": group.saturation_status,
        }
        for group in groups
    ]


def get_conversations_elite(db: Session, username: str | None = None):
    from app.models.lead_conversation import LeadConversation
    from app.models.user import User

    query = db.query(LeadConversation).join(Lead).join(User)
    
    if username:
        query = query.filter(User.username == username)
        
    conversations = query.order_by(desc(LeadConversation.timestamp)).limit(50).all()
    return [
        {
            "lead_id": conversation.lead_id,
            "sender": conversation.sender,
            "message": conversation.message,
            "timestamp": conversation.timestamp,
        }
        for conversation in conversations
    ]


import json

_dashboard_cache = {
    "data": None,
    "timestamp": 0
}
CACHE_TTL = 60 # seconds

def get_dashboard_summary(db: Session) -> DashboardSummary:
    global _dashboard_cache
    now_ts = time.time()
    
    if _dashboard_cache["data"] and (now_ts - _dashboard_cache["timestamp"] < CACHE_TTL):
        return _dashboard_cache["data"]

    today = datetime.utcnow().date()
    now = datetime.utcnow()
    messages_analyzed = db.query(func.count(Message.id)).scalar() or 0

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

    groups_joined = db.query(func.count(Group.id)).filter(Group.joined.is_(True)).scalar() or 0
    leads_detected_total = db.query(func.count(Lead.id)).scalar() or 0
    leads_detected_today = db.query(func.count(Lead.id)).filter(func.date(Lead.created_at) == today).scalar() or 0
    public_replies_sent = db.query(func.count(Lead.id)).filter(Lead.public_reply_sent.is_(True)).scalar() or 0
    dms_sent = db.query(func.count(Lead.id)).filter(Lead.dm_sent.is_(True)).scalar() or 0

    replies_received = (
        db.query(func.count(Lead.id))
        .filter(
            Lead.dm_sent.is_(True),
            Lead.conversion_stage != ConversionStage.CONTACTED,
        )
        .scalar()
        or 0
    )
    reply_rate = (replies_received / dms_sent * 100) if dms_sent > 0 else 0.0

    conversions = db.query(func.count(Lead.id)).filter(Lead.conversion_stage == ConversionStage.CONVERTED).scalar() or 0
    conversion_rate = (conversions / leads_detected_total * 100) if leads_detected_total > 0 else 0.0

    recent_leads_query = (
        db.query(Lead)
        .join(Group, Lead.group_id == Group.id, isouter=True)
        .order_by(Lead.created_at.desc())
        .limit(10)
        .all()
    )
    recent_leads = [
        LeadStats(
            username=lead.user.username if lead.user else None,
            lead_score=lead.lead_score,
            lead_strength=lead.lead_strength,
            status=lead.conversion_stage.value,
            group_name=lead.group.name if lead.group else "Direct/Unknown",
            last_contact=lead.last_contact,
        )
        for lead in recent_leads_query
    ]

    top_groups_query = (
        db.query(
            Group.name,
            Group.messages_last_24h,
            func.count(Lead.id).label("leads_count"),
        )
        .join(Lead, Lead.group_id == Group.id, isouter=True)
        .group_by(Group.id, Group.name, Group.messages_last_24h, Group.authority_score)
        .order_by(desc(Group.authority_score))
        .limit(5)
        .all()
    )
    top_groups = [
        GroupPerformance(
            group_name=row.name,
            leads_generated=row.leads_count,
            messages_scanned=row.messages_last_24h or 0,
        )
        for row in top_groups_query
    ]

    seven_days_ago = today - timedelta(days=7)
    daily_trend_query = (
        db.query(
            func.date(Lead.created_at).label("date"),
            func.count(Lead.id).label("count"),
        )
        .filter(Lead.created_at >= seven_days_ago)
        .group_by(func.date(Lead.created_at))
        .order_by("date")
        .all()
    )
    daily_trend = [DailyTrend(date=str(row.date), count=row.count) for row in daily_trend_query]

    funnel_data = db.query(Lead.conversion_stage, func.count(Lead.id).label("count")).group_by(Lead.conversion_stage).all()
    conversion_funnel = [ConversionFunnel(stage=row.conversion_stage.value, count=row.count) for row in funnel_data]

    elite_stats = get_stats(db)

    summary = DashboardSummary(
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
            .filter(
                FollowUpJob.status == FollowUpJobStatus.QUEUED,
                FollowUpJob.run_at <= now,
            )
            .scalar()
            or 0
        ),
        inbound_messages_today=inbound_messages_today,
        outbound_messages_today=outbound_messages_today,
        groups_joined=groups_joined,
        messages_analyzed=messages_analyzed,
        leads_detected_total=leads_detected_total,
        conversions=conversions,
        leads_detected_today=leads_detected_today,
        public_replies_sent=public_replies_sent,
        dms_sent=dms_sent,
        reply_rate=round(reply_rate, 2),
        conversion_rate=round(conversion_rate, 2),
        high_value_leads=elite_stats.get("high_value_leads", 0),
        reseller_prospects=elite_stats.get("reseller_prospects", 0),
        average_ltv_score=elite_stats.get("average_ltv_score", 0.0),
        ltv_distribution=elite_stats.get("ltv_distribution", {}),
        problem_distribution=elite_stats.get("problem_distribution", {}),
        influence_distribution=elite_stats.get("influence_distribution", {}),
        sentiment_trends=elite_stats.get("sentiment_trends", {}),
        hourly_heatmap=elite_stats.get("hourly_heatmap", []),
        persona_performance=elite_stats.get("persona_performance", []),
        account_health=elite_stats.get("account_health", []),
        recent_leads=recent_leads,
        top_groups=top_groups,
        daily_trend=daily_trend,
        conversion_funnel=conversion_funnel,
    )
    
    _dashboard_cache["data"] = summary
    _dashboard_cache["timestamp"] = now_ts
    return summary
