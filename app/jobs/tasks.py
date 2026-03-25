import logging
from datetime import date, timedelta

from sqlalchemy import func

from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.activity_event import ActivityEvent
from app.models.consent import Consent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.follow_up_job import FollowUpJob
from app.models.lead_profile import LeadProfile
from app.models.message import Message
from app.models.metrics_snapshot import MetricsSnapshot
from app.models.ticket import Ticket
from app.models.enums import (
    ConsentScope,
    ConversationStatus,
    EventType,
    FollowUpJobStatus,
    FollowUpJobType,
    LifecycleStage,
    MessageDirection,
    TicketCategory,
    TicketStatus,
)
from app.services.queue import enqueue_follow_up_job
from app.services.message_scraper import start_message_listener
from app.services.scanner import message_intelligence_scanner
from app.services.response_engine import response_engine
from app.services.reddit_discovery import reddit_lead_discovery
from app.services.power_upgrades import power_upgrades_service
from app.services.group_discovery.discovery_engine import discovery_engine
from app.services.ltv_engine import ltv_engine

logger = logging.getLogger(__name__)

async def slie_power_upgrades():
    """Run Phase 2 Power Upgrades: Opportunity Clustering, Authority Ranking, and Trend Detection (Module 11)."""
    logger.info("Running SLIE power upgrades task...")
    await power_upgrades_service.run_opportunity_clustering()
    await power_upgrades_service.update_group_authority_ranking()
    await power_upgrades_service.run_trend_detection()

async def slie_keyword_discovery():
    """Step 1: Discover new IPTV groups using keywords (Every 6h)."""
    logger.info("Running SLIE Keyword Discovery task...")
    await discovery_engine.run_keyword_search_task()

async def slie_group_analysis():
    """Step 3/4: Analyze discovered group metadata and activity (Every 12h)."""
    logger.info("Running SLIE Group Analysis task...")
    await discovery_engine.run_external_discovery_task()
    await discovery_engine.run_group_analysis_task()

async def slie_join_scheduler():
    """Step 6: Safe Join Scheduler (Every 1h)."""
    logger.info("Running SLIE Join Scheduler task...")
    await discovery_engine.run_join_scheduler_task()

async def slie_ltv_recalculation():
    """Module 16: Recalculate LTV scores for all leads (Every 24h)."""
    logger.info("Running SLIE LTV Recalculation task...")
    await ltv_engine.recalculate_all_scores()

async def slie_message_scanning():
    """Scan messages in joined groups (Non-blocking, starts once)."""
    # Note: In APScheduler, we might want to ensure only one scanner runs
    # For now, we'll start it if not running.
    logger.info("Ensuring SLIE message scraper is running...")
    # This might need a different approach if we want it to be long-running
    # For MVP, we'll just start it.
    await start_message_listener()
    # Keep the intelligence scanner running if it's separate logic
    await message_intelligence_scanner.start_scanning()

async def slie_public_replies():
    """Process pending public replies to leads."""
    logger.info("Running SLIE public replies task...")
    await response_engine.process_public_replies()

async def slie_private_dms():
    """Process pending private DMs to leads."""
    logger.info("Running SLIE private DMs task...")
    await response_engine.process_private_dms()

async def slie_reddit_discovery():
    """Scan Reddit for IPTV complaints."""
    logger.info("Running SLIE Reddit discovery task...")
    await reddit_lead_discovery.discover_reddit_leads()


def _has_active_consent(db, contact_id: str, scope: ConsentScope) -> bool:
    return (
        db.query(Consent)
        .filter(
            Consent.contact_id == contact_id,
            Consent.scope == scope,
            Consent.revoked_at.is_(None),
        )
        .first()
        is not None
    )


def queue_due_follow_ups() -> None:
    now = utcnow()
    with SessionLocal() as db:
        due_tickets = (
            db.query(Ticket)
            .filter(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]),
                Ticket.next_follow_up_at.is_not(None),
                Ticket.next_follow_up_at <= now,
            )
            .all()
        )

        queued = 0
        for ticket in due_tickets:
            scope = ConsentScope.SUPPORT_UPDATES
            job_type = FollowUpJobType.SUPPORT_CHECKIN
            if ticket.category == TicketCategory.DEMO_REQUEST:
                scope = ConsentScope.DEMO_FOLLOW_UPS
                job_type = FollowUpJobType.DEMO_REMINDER
            elif ticket.category == TicketCategory.RESELLER_INQUIRY:
                scope = ConsentScope.RESELLER_PROGRAM
                job_type = FollowUpJobType.RESELLER_FOLLOW_UP

            if not _has_active_consent(db, ticket.contact_id, scope):
                continue

            existing = (
                db.query(FollowUpJob)
                .filter(
                    FollowUpJob.ticket_id == ticket.id,
                    FollowUpJob.status == FollowUpJobStatus.QUEUED,
                )
                .first()
            )
            if existing is not None:
                continue

            job = FollowUpJob(
                contact_id=ticket.contact_id,
                ticket_id=ticket.id,
                job_type=job_type,
                status=FollowUpJobStatus.QUEUED,
                run_at=now,
                payload={"ticket_id": ticket.id, "category": ticket.category.value},
            )
            db.add(job)
            db.flush()
            db.add(
                ActivityEvent(
                    contact_id=ticket.contact_id,
                    event_type=EventType.FOLLOW_UP_QUEUED,
                    occurred_at=now,
                    metadata_json={"job_id": job.id, "ticket_id": ticket.id},
                )
            )
            enqueue_follow_up_job(job.id)
            queued += 1

        db.commit()
        logger.info("Queued %s due follow-up jobs", queued)


def cancel_revoked_follow_ups() -> None:
    now = utcnow()
    with SessionLocal() as db:
        queued_jobs = (
            db.query(FollowUpJob)
            .filter(FollowUpJob.status == FollowUpJobStatus.QUEUED)
            .all()
        )

        cancelled = 0
        for job in queued_jobs:
            scope = ConsentScope.SUPPORT_UPDATES
            if job.job_type == FollowUpJobType.DEMO_REMINDER:
                scope = ConsentScope.DEMO_FOLLOW_UPS
            elif job.job_type == FollowUpJobType.RESELLER_FOLLOW_UP:
                scope = ConsentScope.RESELLER_PROGRAM

            if _has_active_consent(db, job.contact_id, scope):
                continue

            job.status = FollowUpJobStatus.CANCELLED
            db.add(
                ActivityEvent(
                    contact_id=job.contact_id,
                    event_type=EventType.FOLLOW_UP_CANCELLED,
                    occurred_at=now,
                    metadata_json={"job_id": job.id, "reason": "consent_missing_or_revoked"},
                )
            )
            cancelled += 1

        db.commit()
        logger.info("Cancelled %s queued jobs after consent review", cancelled)


def refresh_engagement_scores() -> None:
    now = utcnow()
    recent_cutoff = now - timedelta(days=30)

    with SessionLocal() as db:
        contacts = db.query(Contact).all()
        for contact in contacts:
            recent_inbound = (
                db.query(func.count(Message.id))
                .filter(
                    Message.contact_id == contact.id,
                    Message.direction == MessageDirection.INBOUND,
                    Message.sent_at >= recent_cutoff,
                )
                .scalar()
                or 0
            )
            open_tickets = (
                db.query(func.count(Ticket.id))
                .filter(
                    Ticket.contact_id == contact.id,
                    Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]),
                )
                .scalar()
                or 0
            )
            active_consents = (
                db.query(func.count(Consent.id))
                .filter(
                    Consent.contact_id == contact.id,
                    Consent.revoked_at.is_(None),
                )
                .scalar()
                or 0
            )

            score = int(recent_inbound * 2 + open_tickets * 5 + active_consents * 3)
            profile = (
                db.query(LeadProfile)
                .filter(LeadProfile.contact_id == contact.id)
                .one_or_none()
            )
            if profile is None:
                profile = LeadProfile(contact_id=contact.id)
                db.add(profile)

            profile.engagement_score = score
            profile.last_scored_at = now
            if open_tickets > 0:
                profile.lifecycle_stage = LifecycleStage.SUPPORT_ACTIVE
            elif active_consents > 0 and recent_inbound > 0:
                profile.lifecycle_stage = LifecycleStage.QUALIFIED
            else:
                profile.lifecycle_stage = LifecycleStage.NEW

        db.commit()
        logger.info("Refreshed engagement scores for %s contacts", len(contacts))


def close_stale_conversations() -> None:
    now = utcnow()
    stale_cutoff = now - timedelta(days=14)

    with SessionLocal() as db:
        conversations = (
            db.query(Conversation)
            .filter(
                Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]),
                Conversation.updated_at <= stale_cutoff,
            )
            .all()
        )

        closed = 0
        for conversation in conversations:
            open_ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.conversation_id == conversation.id,
                    Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]),
                )
                .first()
            )
            if open_ticket is not None:
                continue
            conversation.status = ConversationStatus.CLOSED
            conversation.closed_at = now
            db.add(
                ActivityEvent(
                    contact_id=conversation.contact_id,
                    event_type=EventType.CONVERSATION_CLOSED,
                    occurred_at=now,
                    metadata_json={"conversation_id": conversation.id, "reason": "stale"},
                )
            )
            closed += 1

        db.commit()
        logger.info("Closed %s stale conversations", closed)


def snapshot_daily_metrics() -> None:
    today = date.today()
    with SessionLocal() as db:
        snapshot = db.query(MetricsSnapshot).filter(MetricsSnapshot.day == today).one_or_none()
        if snapshot is None:
            snapshot = MetricsSnapshot(day=today)
            db.add(snapshot)

        snapshot.contacts_total = db.query(func.count(Contact.id)).scalar() or 0
        snapshot.open_conversations = (
            db.query(func.count(Conversation.id))
            .filter(Conversation.status.in_([ConversationStatus.OPEN, ConversationStatus.PENDING]))
            .scalar()
            or 0
        )
        snapshot.open_tickets = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.status.in_([TicketStatus.OPEN, TicketStatus.PENDING]))
            .scalar()
            or 0
        )
        snapshot.inbound_messages = (
            db.query(func.count(Message.id))
            .filter(
                Message.direction == MessageDirection.INBOUND,
                func.date(Message.sent_at) == today,
            )
            .scalar()
            or 0
        )
        snapshot.outbound_messages = (
            db.query(func.count(Message.id))
            .filter(
                Message.direction == MessageDirection.OUTBOUND,
                func.date(Message.sent_at) == today,
            )
            .scalar()
            or 0
        )
        snapshot.follow_ups_due = (
            db.query(func.count(FollowUpJob.id))
            .filter(FollowUpJob.status == FollowUpJobStatus.QUEUED)
            .scalar()
            or 0
        )

        db.commit()
        logger.info("Updated daily metrics snapshot for %s", today.isoformat())
