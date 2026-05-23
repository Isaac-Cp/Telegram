import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.follow_up_job import FollowUpJob
from app.models.enums import FollowUpJobStatus, FollowUpJobType
from app.services.email import email_service
from app.core.redis import get_redis_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class FollowUpWorker:
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = get_redis_client()
        self.is_running = False

    async def start(self):
        """Starts the worker loop."""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Follow-Up Worker started.")
        
        while self.is_running:
            try:
                # Use blpop for efficient polling (blocks for 5 seconds)
                job_data = self.redis_client.blpop("follow_up_jobs", timeout=5)
                if job_data:
                    job_id = job_data[1]
                    await self._process_job(job_id)
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(5)

    def stop(self):
        self.is_running = False

    async def _process_job(self, job_id: str):
        """Processes a single follow-up job."""
        with SessionLocal() as db:
            job = db.get(FollowUpJob, job_id)
            if not job or job.status != FollowUpJobStatus.QUEUED:
                return

            logger.info(f"Processing follow-up job: {job_id} (Type: {job.job_type})")
            job.status = FollowUpJobStatus.PROCESSING
            db.commit()

            success = False
            try:
                if job.job_type == FollowUpJobType.SUPPORT_CHECKIN:
                    success = await self._handle_support_checkin(job)
                elif job.job_type == FollowUpJobType.DEMO_REMINDER:
                    success = await self._handle_demo_reminder(job)
                elif job.job_type == FollowUpJobType.RESELLER_FOLLOW_UP:
                    success = await self._handle_reseller_follow_up(job)
                
                job.status = FollowUpJobStatus.COMPLETED if success else FollowUpJobStatus.FAILED
                job.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Job {job_id} {job.status}")
            except Exception as e:
                logger.error(f"Failed to process job {job_id}: {e}")
                job.status = FollowUpJobStatus.FAILED
                db.commit()

    async def _handle_support_checkin(self, job: FollowUpJob) -> bool:
        # For now, let's assume we send an email to the admin or the user
        # In a real scenario, we'd fetch the contact's email if available
        # Since the models don't have an email field on Contact yet, we'll use a placeholder or admin email
        to_email = self.settings.admin_email
        if not to_email:
            logger.warning("No admin email configured for support check-in.")
            return False

        subject = f"Support Check-in: Ticket {job.ticket_id}"
        body = f"Automated check-in for support ticket {job.ticket_id}. Please review the status."
        return email_service.send_email(to_email, subject, body)

    async def _handle_demo_reminder(self, job: FollowUpJob) -> bool:
        to_email = self.settings.admin_email
        if not to_email:
            return False
        subject = f"Demo Reminder: Ticket {job.ticket_id}"
        body = f"Reminder for demo request ticket {job.ticket_id}."
        return email_service.send_email(to_email, subject, body)

    async def _handle_reseller_follow_up(self, job: FollowUpJob) -> bool:
        to_email = self.settings.admin_email
        if not to_email:
            return False
        subject = f"Reseller Follow-up: Ticket {job.ticket_id}"
        body = f"Follow-up for reseller inquiry ticket {job.ticket_id}."
        return email_service.send_email(to_email, subject, body)

follow_up_worker = FollowUpWorker()
