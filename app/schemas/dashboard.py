from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, Any

class LeadStats(BaseModel):
    username: Optional[str]
    lead_score: int
    lead_strength: Optional[str]
    status: str
    group_name: Optional[str]
    last_contact: Optional[datetime]

class GroupPerformance(BaseModel):
    group_name: str
    leads_generated: int
    messages_scanned: int

class DailyTrend(BaseModel):
    date: str
    count: int

class ConversionFunnel(BaseModel):
    stage: str
    count: int

class PersonaPerformance(BaseModel):
    name: str
    leads: int
    conversions: int
    rate: float

class AccountHealth(BaseModel):
    phone: str
    status: str
    dms_used: int
    replies_used: int
    joins_used: int
    dms_left: int = 0
    replies_left: int = 0
    joins_left: int = 0
    proxy_status: bool = True
    cooldown_until: Optional[datetime] = None

class DashboardSummary(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_source: str = "database"
    contacts_total: int
    active_consents: int
    open_conversations: int
    open_tickets: int
    follow_ups_due: int
    inbound_messages_today: int
    outbound_messages_today: int
    
    # SLIE Metrics
    groups_joined: int
    messages_analyzed: int
    leads_detected_total: int
    conversions: int
    leads_detected_today: int
    public_replies_sent: int
    dms_sent: int
    reply_rate: float
    conversion_rate: float
    high_prob_leads: int = 0
    high_value_leads: int
    reseller_prospects: int
    average_ltv_score: float
    ltv_distribution: dict[str, int]
    problem_distribution: dict[str, int]
    influence_distribution: dict[str, int]
    sentiment_trends: dict[str, dict[str, int]]
    hourly_heatmap: list[dict[str, Any]]
    persona_performance: list[dict[str, Any]]
    account_health: list[dict[str, Any]]
    competitor_stats: list[dict[str, Any]] = Field(default_factory=list)
    activity_log: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    crm_trend: list[dict[str, Any]] = Field(default_factory=list)
    ticket_status_breakdown: dict[str, int] = Field(default_factory=dict)
    ticket_priority_breakdown: dict[str, int] = Field(default_factory=dict)
    consent_scope_breakdown: dict[str, int] = Field(default_factory=dict)
    lifecycle_stage_breakdown: dict[str, int] = Field(default_factory=dict)
    recent_leads: list[LeadStats]
    top_groups: list[GroupPerformance]
    daily_trend: list[DailyTrend]
    conversion_funnel: list[ConversionFunnel]
