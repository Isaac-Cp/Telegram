from datetime import date, timedelta
import logging

from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

from app.intelligence.models.competitor_models import CompetitorInsight
from app.intelligence.models.conversion_models import ConversionPrediction
from app.intelligence.models.influence_models import InfluenceProfile
from app.models.consent import Consent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_memory import LeadValueScore, UnifiedConversation
from app.models.enums import ConversationStatus, ConversionStage, FollowUpJobStatus, MessageDirection, TicketStatus
from app.models.follow_up_job import FollowUpJob
from app.models.group import Group
from app.models.lead import Lead
from app.models.message import Message
from app.models.problem_trend import ProblemTrend
from app.models.telegram_account import TelegramAccount
from app.models.ticket import Ticket
from app.schemas.dashboard import (
    AccountHealth,
    ConversionFunnel,
    DailyTrend,
    DashboardSummary,
    GroupPerformance,
    LeadStats,
    PersonaPerformance,
)

logger = logging.getLogger(__name__)

FRONTEND_REPLY_LIMIT = 5
FRONTEND_DM_LIMIT = 10
FRONTEND_JOIN_LIMIT = 2


def _get_ltv_distribution(db: Session) -> dict[str, int]:
    rows = (
        db.query(
            LeadValueScore.ltv_tier,
            func.count(LeadValueScore.id).label("count"),
        )
        .group_by(LeadValueScore.ltv_tier)
        .all()
    )
    return {row.ltv_tier or "UNKNOWN": row.count for row in rows}


def _get_frontend_account_health(db: Session) -> list[dict[str, int | str]]:
    accounts = db.query(TelegramAccount).all()
    return [
        {
            "phone": account.phone_number,
            "status": account.status,
            "replies_left": max(0, FRONTEND_REPLY_LIMIT - account.daily_reply_count),
            "dms_left": max(0, FRONTEND_DM_LIMIT - account.daily_dm_count),
            "joins_left": max(0, FRONTEND_JOIN_LIMIT - account.groups_joined),
        }
        for account in accounts
    ]


def _get_summary_account_health(db: Session) -> list[AccountHealth]:
    accounts = db.query(TelegramAccount).all()
    return [
        AccountHealth(
            phone=account.phone_number,
            status=account.status,
            dms_used=account.daily_dm_count,
            replies_used=account.daily_reply_count,
            joins_used=account.groups_joined,
        )
        for account in accounts
    ]


def _get_persona_performance(db: Session) -> list[PersonaPerformance]:
    rows = (
        db.query(
            Lead.persona_id.label("name"),
            func.count(Lead.id).label("leads"),
            func.sum(
                case(
                    (Lead.conversion_stage == ConversionStage.CONVERTED, 1),
                    else_=0,
                )
            ).label("conversions"),
        )
        .filter(Lead.persona_id.is_not(None))
        .group_by(Lead.persona_id)
        .order_by(desc("leads"))
        .all()
    )
    return [
        PersonaPerformance(
            name=row.name,
            leads=row.leads,
            conversions=int(row.conversions or 0),
            rate=round(((row.conversions or 0) / row.leads) * 100, 2) if row.leads else 0.0,
        )
        for row in rows
    ]


def _get_problem_distribution(db: Session) -> dict[str, int]:
    rows = (
        db.query(
            ProblemTrend.problem_type,
            func.sum(ProblemTrend.occurrence_count).label("count"),
        )
        .group_by(ProblemTrend.problem_type)
        .all()
    )
    return {row.problem_type: row.count for row in rows}


def get_stats(db: Session):
    """
    Elite Module 12: Performance tracking metrics.
    """
    total_groups_joined = db.query(func.count(Group.id)).filter(Group.joined.is_(True)).scalar() or 0
    messages_analyzed = db.query(func.count(Message.id)).scalar() or 0
    leads_detected = db.query(func.count(Lead.id)).scalar() or 0
    dms_sent = db.query(func.count(Lead.id)).filter(Lead.dm_sent.is_(True)).scalar() or 0
    conversions = (
        db.query(func.count(Lead.id))
        .filter(Lead.conversion_stage == ConversionStage.CONVERTED)
        .scalar()
        or 0
    )
    conversion_rate = (conversions / leads_detected * 100) if leads_detected > 0 else 0

    influence_distribution = {
        "leader": (
            db.query(func.count(InfluenceProfile.id))
            .filter(InfluenceProfile.influence_level == "community_leader")
            .scalar()
            or 0
        ),
        "power_user": (
            db.query(func.count(InfluenceProfile.id))
            .filter(InfluenceProfile.influence_level == "power_user")
            .scalar()
            or 0
        ),
        "regular": (
            db.query(func.count(InfluenceProfile.id))
            .filter(InfluenceProfile.influence_level == "regular_member")
            .scalar()
            or 0
        ),
    }

    top_competitors = (
        db.query(CompetitorInsight)
        .order_by(desc(CompetitorInsight.weakness_score))
        .limit(5)
        .all()
    )
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

    recent_activity = (
        db.query(UnifiedConversation)
        .order_by(desc(UnifiedConversation.timestamp))
        .limit(10)
        .all()
    )
    activity_log = [
        {
            "user": activity.user.username if activity.user else "Unknown",
            "type": activity.message_type,
            "text": activity.message_text[:50] + "..." if len(activity.message_text) > 50 else activity.message_text,
            "time": activity.timestamp.strftime("%H:%M:%S"),
        }
        for activity in recent_activity
    ]

    average_ltv_score = db.query(func.avg(LeadValueScore.ltv_score)).scalar() or 0.0
    reseller_prospects = (
        db.query(func.count(LeadValueScore.id))
        .filter(LeadValueScore.ltv_tier == "RESELLER POTENTIAL")
        .scalar()
        or 0
    )
    high_value_leads = (
        db.query(func.count(LeadValueScore.id))
        .filter(LeadValueScore.ltv_tier.in_(["HIGH VALUE BUYER", "RESELLER POTENTIAL"]))
        .scalar()
        or 0
    )

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
        "ltv_distribution": _get_ltv_distribution(db),
        "problem_distribution": _get_problem_distribution(db),
        "persona_performance": _get_persona_performance(db),
        "account_health": _get_frontend_account_health(db),
        "activity_log": activity_log,
        "dms_sent": dms_sent,
    }


def get_conversions_elite(db: Session):
    """Elite Module 12 conversions list."""
    converted_leads = db.query(Lead).filter(Lead.conversion_stage == ConversionStage.CONVERTED).all()
    return [
        {
            "username": lead.username,
            "temperature": lead.lead_temperature,
            "last_contact": lead.last_contact,
            "score": lead.lead_score,
        }
        for lead in converted_leads
    ]


def get_reseller_prospects_elite(db: Session):
    """Elite Module 16: Get top reseller prospects."""
    prospects = (
        db.query(Lead, LeadValueScore)
        .join(LeadValueScore, LeadValueScore.user_id == Lead.user_id)
        .filter(LeadValueScore.ltv_tier == "RESELLER POTENTIAL")
        .order_by(desc(LeadValueScore.ltv_score))
        .limit(10)
        .all()
    )

    return [
        {
            "username": lead.username,
            "score": score.ltv_score,
            "level": score.ltv_tier,
            "last_updated": score.last_updated,
        }
        for lead, score in prospects
    ]


def get_leads_elite(db: Session):
    """Module 16 elite leads list."""
    leads = db.query(Lead).order_by(desc(Lead.lead_score)).limit(50).all()
    return [
        {
            "username": lead.username,
            "score": lead.lead_score,
            "temperature": lead.lead_temperature,
            "status": lead.conversion_stage.value,
            "last_contact": lead.last_contact,
        }
        for lead in leads
    ]


def get_groups_elite(db: Session):
    """Elite Module 12 and 14 groups list."""
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


def get_conversations_elite(db: Session):
    """Module 16 elite conversations history."""
    from app.models.lead_conversation import LeadConversation

    conversations = db.query(LeadConversation).order_by(desc(LeadConversation.timestamp)).limit(50).all()
    return [
        {
            "lead_id": conversation.lead_id,
            "sender": conversation.sender,
            "message": conversation.message,
            "timestamp": conversation.timestamp,
        }
        for conversation in conversations
    ]


def get_dashboard_summary(db: Session) -> DashboardSummary:
    today = date.today()

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
    leads_detected_today = (
        db.query(func.count(Lead.id))
        .filter(func.date(Lead.created_at) == today)
        .scalar()
        or 0
    )
    public_replies_sent = (
        db.query(func.count(Lead.id))
        .filter(Lead.public_reply_sent.is_(True))
        .scalar()
        or 0
    )
    dms_sent = db.query(func.count(Lead.id)).filter(Lead.dm_sent.is_(True)).scalar() or 0
    replies_received = (
        db.query(func.count(Lead.id))
        .filter(
            Lead.dm_sent.is_(True),
            Lead.conversion_stage.in_([ConversionStage.RESPONDED, ConversionStage.CONVERTED]),
        )
        .scalar()
        or 0
    )
    reply_rate = (replies_received / dms_sent * 100) if dms_sent > 0 else 0.0
    conversions = (
        db.query(func.count(Lead.id))
        .filter(Lead.conversion_stage == ConversionStage.CONVERTED)
        .scalar()
        or 0
    )
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
            username=lead.username,
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
            Group.authority_score,
            Group.messages_last_24h,
            func.count(Lead.id).label("leads_count"),
        )
        .join(Lead, Lead.group_id == Group.id, isouter=True)
        .group_by(Group.id, Group.name, Group.authority_score, Group.messages_last_24h)
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

    funnel_rows = (
        db.query(
            Lead.conversion_stage,
            func.count(Lead.id).label("count"),
        )
        .group_by(Lead.conversion_stage)
        .all()
    )
    conversion_funnel = [
        ConversionFunnel(stage=row.conversion_stage.value, count=row.count)
        for row in funnel_rows
    ]

    elite_stats = get_stats(db)

    return DashboardSummary(
        contacts_total=db.query(func.count(Contact.id)).scalar() or 0,
        active_consents=(
            db.query(func.count(Consent.id))
            .filter(Consent.revoked_at.is_(None))
            .scalar()
            or 0
        ),
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
            .filter(FollowUpJob.status == FollowUpJobStatus.QUEUED)
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
        reply_rate=round(reply_rate, 2),
        conversion_rate=round(conversion_rate, 2),
        high_value_leads=elite_stats["high_value_leads"],
        reseller_prospects=elite_stats["reseller_prospects"],
        average_ltv_score=elite_stats["average_ltv_score"],
        ltv_distribution=elite_stats["ltv_distribution"],
        problem_distribution=elite_stats["problem_distribution"],
        persona_performance=elite_stats["persona_performance"],
        account_health=_get_summary_account_health(db),
        recent_leads=recent_leads,
        top_groups=top_groups,
        daily_trend=daily_trend,
        conversion_funnel=conversion_funnel,
    )
