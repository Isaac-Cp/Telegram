"""
Database Cleanup and Data Retention Service

This service automatically removes old data from the database to prevent growth and crashes.
It implements smart data retention policies that keep important data while removing transactional records.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.data_retention import RetentionConfig, TABLE_RETENTION_MAP, DataRetentionPolicy
from app.models.activity_event import ActivityEvent
from app.models.conversation import Conversation
from app.models.conversation_memory import UnifiedConversation, ConversationSummary
from app.models.follow_up_job import FollowUpJob
from app.models.group_join_history import GroupJoinHistory
from app.models.lead_conversation import LeadConversation
from app.models.message import Message
from app.models.message_analysis import MessageAnalysis
from app.models.metrics_snapshot import MetricsSnapshot
from app.models.opportunity_cluster import OpportunityCluster
from app.models.problem_trend import ProblemTrend
from app.models.cross_group_identity import CrossGroupIdentity
from app.models.external_lead import ExternalLead

logger = logging.getLogger(__name__)


class DatabaseCleanupService:
    """Service for managing database cleanup and data retention"""
    
    def __init__(self, retention_config: Optional[RetentionConfig] = None):
        self.config = retention_config or RetentionConfig()
        self.logger = logging.getLogger(__name__)
    
    async def cleanup_messages(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """
        Delete old messages beyond retention period
        
        Args:
            session: Database session
            days: Retention days (defaults to config)
            
        Returns:
            Number of messages deleted
        """
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.MESSAGES_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            # Delete old messages (this will cascade to message_analysis)
            stmt = delete(Message).where(Message.sent_at < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old messages (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting messages: {e}")
            await session.rollback()
            return 0
    
    async def cleanup_activity_events(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old activity events"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.ACTIVITY_EVENTS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(ActivityEvent).where(ActivityEvent.occurred_at < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old activity events (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting activity events: {e}")
            await session.rollback()
            return 0
    
    async def cleanup_unified_conversations(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old unified conversation history"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.UNIFIED_CONVERSATIONS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(UnifiedConversation).where(UnifiedConversation.timestamp < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old conversation history records (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting conversation history: {e}")
            await session.rollback()
            return 0
    
    async def cleanup_follow_up_jobs(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete completed follow-up jobs older than retention period"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.FOLLOW_UP_JOBS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            # Delete only completed follow-up jobs
            from app.models.enums import FollowUpJobStatus
            stmt = delete(FollowUpJob).where(
                and_(
                    FollowUpJob.created_at < cutoff_date,
                    FollowUpJob.status.in_([
                        FollowUpJobStatus.COMPLETED,
                        FollowUpJobStatus.CANCELLED,
                        FollowUpJobStatus.FAILED
                    ])
                )
            )
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old follow-up jobs (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting follow-up jobs: {e}")
            await session.rollback()
            return 0
    
    async def cleanup_group_join_history(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old group join history"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.GROUP_JOIN_HISTORY_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(GroupJoinHistory).where(GroupJoinHistory.join_time < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old group join records (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting group join history: {e}")
            await session.rollback()
            return 0
    
    async def cleanup_old_metrics(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old daily metrics snapshots"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.METRICS_SNAPSHOTS_RETENTION_DAYS
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()
        
        try:
            stmt = delete(MetricsSnapshot).where(MetricsSnapshot.day < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old metrics snapshots (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting metrics snapshots: {e}")
            await session.rollback()
            return 0
    
    async def cleanup_lead_conversations(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old lead conversation history"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.UNIFIED_CONVERSATIONS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(LeadConversation).where(LeadConversation.timestamp < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old lead conversation records (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting lead conversations: {e}")
            await session.rollback()
            return 0

    async def cleanup_opportunity_clusters(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old opportunity clusters"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.OPPORTUNITY_CLUSTERS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(OpportunityCluster).where(OpportunityCluster.timestamp < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old opportunity clusters (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting opportunity clusters: {e}")
            await session.rollback()
            return 0

    async def cleanup_problem_trends(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old problem trends"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.PROBLEM_TRENDS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(ProblemTrend).where(ProblemTrend.timestamp < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old problem trends (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting problem trends: {e}")
            await session.rollback()
            return 0

    async def cleanup_cross_group_identities(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old cross-group identities not seen recently"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.CROSS_GROUP_IDENTITIES_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(CrossGroupIdentity).where(CrossGroupIdentity.last_seen_in_group < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old cross-group identity records (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting cross-group identities: {e}")
            await session.rollback()
            return 0

    async def cleanup_external_leads(self, session: AsyncSession, days: Optional[int] = None) -> int:
        """Delete old external leads"""
        if not self.config.CLEANUP_ENABLED:
            return 0
        
        days = days or self.config.EXTERNAL_LEADS_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            stmt = delete(ExternalLead).where(ExternalLead.timestamp < cutoff_date)
            result = await session.execute(stmt)
            deleted = result.rowcount
            
            await session.commit()
            if deleted > 0:
                self.logger.info(f"✓ Deleted {deleted} old external leads (older than {days} days)")
            
            return deleted
        except Exception as e:
            self.logger.error(f"✗ Error deleting external leads: {e}")
            await session.rollback()
            return 0
    
    async def run_full_cleanup(self, session: AsyncSession) -> dict:
        """
        Run all cleanup operations
        
        Returns:
            Dictionary with statistics on deleted records
        """
        if not self.config.CLEANUP_ENABLED:
            self.logger.warning("Database cleanup is disabled in configuration")
            return {}
        
        stats = {
            "messages": await self.cleanup_messages(session),
            "activity_events": await self.cleanup_activity_events(session),
            "conversation_history": await self.cleanup_unified_conversations(session),
            "lead_conversations": await self.cleanup_lead_conversations(session),
            "follow_up_jobs": await self.cleanup_follow_up_jobs(session),
            "group_join_history": await self.cleanup_group_join_history(session),
            "metrics_snapshots": await self.cleanup_old_metrics(session),
            "opportunity_clusters": await self.cleanup_opportunity_clusters(session),
            "problem_trends": await self.cleanup_problem_trends(session),
            "cross_group_identities": await self.cleanup_cross_group_identities(session),
            "external_leads": await self.cleanup_external_leads(session),
            "total": 0
        }
        
        stats["total"] = sum(v for k, v in stats.items() if k != "total")
        
        if stats["total"] > 0:
            self.logger.info(f"🧹 Database cleanup complete: {stats['total']} total records deleted")
        
        return stats
    
    async def get_database_size_estimate(self, session: AsyncSession) -> dict:
        """
        Estimate database table sizes (PostgreSQL specific)
        
        Returns:
            Dictionary with table sizes in MB
        """
        from sqlalchemy import text
        
        try:
            query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)
            
            result = await session.execute(query)
            rows = result.fetchall()
            
            sizes = {}
            for row in rows:
                sizes[row[1]] = row[2]
            
            return sizes
        except Exception as e:
            self.logger.error(f"Could not get database size estimate: {e}")
            return {}
    
    async def get_cleanup_recommendations(self, session: AsyncSession) -> list:
        """
        Analyze database and provide cleanup recommendations
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        try:
            # Count old messages
            from sqlalchemy import func
            cutoff = datetime.utcnow() - timedelta(days=self.config.MESSAGES_RETENTION_DAYS)
            
            stmt = select(func.count(Message.id)).where(Message.sent_at < cutoff)
            result = await session.execute(stmt)
            old_messages = result.scalar() or 0
            
            if old_messages > 0:
                recommendations.append(
                    f"⚠️  {old_messages} messages older than {self.config.MESSAGES_RETENTION_DAYS} days can be deleted"
                )
            
            # Count old activity events
            cutoff = datetime.utcnow() - timedelta(days=self.config.ACTIVITY_EVENTS_RETENTION_DAYS)
            stmt = select(func.count(ActivityEvent.id)).where(ActivityEvent.occurred_at < cutoff)
            result = await session.execute(stmt)
            old_events = result.scalar() or 0
            
            if old_events > 0:
                recommendations.append(
                    f"⚠️  {old_events} activity events older than {self.config.ACTIVITY_EVENTS_RETENTION_DAYS} days can be deleted"
                )
            
        except Exception as e:
            self.logger.error(f"Error generating cleanup recommendations: {e}")
        
        return recommendations
