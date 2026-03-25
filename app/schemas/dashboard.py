from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

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

class DashboardSummary(BaseModel):
    contacts_total: int
    active_consents: int
    open_conversations: int
    open_tickets: int
    follow_ups_due: int
    inbound_messages_today: int
    outbound_messages_today: int
    
    # SLIE Metrics
    groups_joined: int
    leads_detected_total: int
    leads_detected_today: int
    public_replies_sent: int
    dms_sent: int
    reply_rate: float
    conversion_rate: float
    
    # Elite Upgrade Metrics
    high_value_leads: int
    reseller_prospects: int
    average_ltv_score: float
    ltv_distribution: dict
    problem_distribution: dict
    persona_performance: List[PersonaPerformance]
    account_health: List[AccountHealth]
    
    # New detailed data
    recent_leads: List[LeadStats]
    top_groups: List[GroupPerformance]
    daily_trend: List[DailyTrend]
    conversion_funnel: List[ConversionFunnel]
