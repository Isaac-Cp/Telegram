"""
Data Retention Policy Configuration

This module defines how long different types of data are retained in the database.
Older data is automatically deleted to prevent database bloat.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class DataRetentionPolicy(Enum):
    """Retention policy levels"""
    PERMANENT = "permanent"  # Never delete
    LONG_TERM = "long_term"  # Keep for 1 year
    MEDIUM_TERM = "medium_term"  # Keep for 90 days
    SHORT_TERM = "short_term"  # Keep for 30 days
    TEMPORARY = "temporary"  # Keep for 7 days


@dataclass
class RetentionConfig:
    """Configuration for data retention policies"""
    
    # ===== CRITICAL DATA (PERMANENT) =====
    # These tables store core business data and should never be deleted
    CONTACTS_RETENTION_DAYS: int = 99999  # Effectively permanent
    LEADS_RETENTION_DAYS: int = 99999
    USERS_RETENTION_DAYS: int = 99999
    GROUPS_RETENTION_DAYS: int = 99999
    PERSONAS_RETENTION_DAYS: int = 99999
    LEAD_PROFILES_RETENTION_DAYS: int = 99999
    LEAD_OPPORTUNITIES_RETENTION_DAYS: int = 99999
    TICKETS_RETENTION_DAYS: int = 99999
    CONVERSATIONS_RETENTION_DAYS: int = 99999  # Keep all conversations
    
    # ===== IMPORTANT ANALYTICAL DATA (1 YEAR) =====
    # These store important insights but can be archived after a year
    PROBLEM_TRENDS_RETENTION_DAYS: int = 365
    OPPORTUNITY_CLUSTERS_RETENTION_DAYS: int = 365
    LEAD_VALUE_SCORES_RETENTION_DAYS: int = 99999  # Keep latest scores
    METRICS_SNAPSHOTS_RETENTION_DAYS: int = 365  # Keep 1 year of daily metrics
    
    # ===== TRANSACTIONAL DATA (30-90 DAYS) =====
    # These grow quickly and should be pruned regularly
    MESSAGES_RETENTION_DAYS: int = 90  # Keep messages for 90 days
    MESSAGE_ANALYSIS_RETENTION_DAYS: int = 90  # Keep analysis with messages
    ACTIVITY_EVENTS_RETENTION_DAYS: int = 90  # Keep events for 90 days
    
    # ===== CONVERSATION MEMORY (30 DAYS) =====
    # These are working memory for conversations
    UNIFIED_CONVERSATIONS_RETENTION_DAYS: int = 30  # Keep recent conversation history
    EXTERNAL_LEADS_RETENTION_DAYS: int = 30  # Prune external leads after 30 days
    
    # ===== LESS CRITICAL DATA (90 DAYS) =====
    GROUP_JOIN_HISTORY_RETENTION_DAYS: int = 90  # Track join history for 90 days
    FOLLOW_UP_JOBS_RETENTION_DAYS: int = 30  # Clean up completed follow-ups after 30 days
    CROSS_GROUP_IDENTITIES_RETENTION_DAYS: int = 365  # Cross-group mapping
    CONVERSATION_SUMMARY_RETENTION_DAYS: int = 99999  # Keep summary indefinitely
    CONSENT_RETENTION_DAYS: int = 99999  # Keep consent records (legal requirement)
    
    # ===== CLEANUP SETTINGS =====
    # Run cleanup daily to keep database small
    CLEANUP_BATCH_SIZE: int = 1000  # Delete in batches to avoid locking
    CLEANUP_ENABLED: bool = True
    
    @classmethod
    def get_retention_days(cls, table_name: str) -> int:
        """Get retention days for a specific table"""
        config = cls()
        attr_name = f"{table_name.upper()}_RETENTION_DAYS"
        
        if hasattr(config, attr_name):
            return getattr(config, attr_name)
        
        # Default to 30 days if not specified
        return 30
    
    @classmethod
    def get_retention_timedelta(cls, table_name: str) -> timedelta:
        """Get retention period as timedelta"""
        return timedelta(days=cls.get_retention_days(table_name))


# Table mapping for easier access
TABLE_RETENTION_MAP = {
    # Permanent
    "contacts": DataRetentionPolicy.PERMANENT,
    "leads": DataRetentionPolicy.PERMANENT,
    "users": DataRetentionPolicy.PERMANENT,
    "groups": DataRetentionPolicy.PERMANENT,
    "personas": DataRetentionPolicy.PERMANENT,
    "lead_profiles": DataRetentionPolicy.PERMANENT,
    "lead_opportunities": DataRetentionPolicy.PERMANENT,
    "tickets": DataRetentionPolicy.PERMANENT,
    "conversations": DataRetentionPolicy.PERMANENT,
    "conversation_summary": DataRetentionPolicy.PERMANENT,
    "consent": DataRetentionPolicy.PERMANENT,
    
    # Long term (1 year)
    "problem_trends": DataRetentionPolicy.LONG_TERM,
    "opportunity_clusters": DataRetentionPolicy.LONG_TERM,
    "metrics_snapshots": DataRetentionPolicy.LONG_TERM,
    "cross_group_identities": DataRetentionPolicy.LONG_TERM,
    
    # Medium term (90 days)
    "messages": DataRetentionPolicy.MEDIUM_TERM,
    "message_analysis": DataRetentionPolicy.MEDIUM_TERM,
    "activity_events": DataRetentionPolicy.MEDIUM_TERM,
    "group_join_history": DataRetentionPolicy.MEDIUM_TERM,
    
    # Short term (30 days)
    "unified_conversations": DataRetentionPolicy.SHORT_TERM,
    "follow_up_jobs": DataRetentionPolicy.SHORT_TERM,
    "external_leads": DataRetentionPolicy.SHORT_TERM,
}
