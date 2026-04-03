from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Iterable

from app.services.group_discovery.discovery_config import (
    BUYER_AUDIENCE_KEYWORDS,
    BUYER_INTENT_KEYWORDS,
    COMPETITOR_PAIN_SIGNALS,
    GROUP_QUALITY_THRESHOLDS,
    SELLER_PROMOTION_KEYWORDS,
)

URL_PATTERN = re.compile(r"(https?://|t\.me/|telegram\.me/|www\.)", re.IGNORECASE)


@dataclass(frozen=True)
class SampledMessage:
    text: str
    sender_id: str | None
    sent_at: datetime | None
    is_reply: bool = False


@dataclass
class GroupActivityMetrics:
    total_messages: int = 0
    messages_last_24h: int = 0
    recent_messages_6h: int = 0
    unique_users_last_24h: int = 0
    buyer_signal_count: int = 0
    pain_signal_count: int = 0
    seller_signal_count: int = 0
    question_count: int = 0
    reply_count: int = 0
    duplicate_promo_count: int = 0
    link_count: int = 0
    last_message_at: datetime | None = None

    @property
    def seller_density(self) -> float:
        return (self.seller_signal_count / self.total_messages) if self.total_messages else 0.0

    @property
    def buyer_density(self) -> float:
        return (self.buyer_signal_count / self.total_messages) if self.total_messages else 0.0

    @property
    def pain_density(self) -> float:
        return (self.pain_signal_count / self.total_messages) if self.total_messages else 0.0

    @property
    def question_ratio(self) -> float:
        return (self.question_count / self.total_messages) if self.total_messages else 0.0

    @property
    def reply_ratio(self) -> float:
        return (self.reply_count / self.total_messages) if self.total_messages else 0.0

    @property
    def conversation_ratio(self) -> float:
        if not self.total_messages:
            return 0.0
        return min(1.0, self.question_ratio + (self.reply_ratio * 0.75))

    @property
    def duplicate_promo_ratio(self) -> float:
        return (self.duplicate_promo_count / self.total_messages) if self.total_messages else 0.0


@dataclass
class GroupQualityDecision:
    score: int
    status: str
    eligible: bool
    market_type: str
    reasons: list[str] = field(default_factory=list)
    seller_density: float = 0.0
    buyer_density: float = 0.0
    conversation_ratio: float = 0.0


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def analyze_sampled_messages(messages: list[SampledMessage], now: datetime | None = None) -> GroupActivityMetrics:
    now = now or datetime.utcnow()
    day_cutoff = now - timedelta(hours=24)
    recent_cutoff = now - timedelta(hours=6)

    metrics = GroupActivityMetrics(total_messages=len(messages))
    unique_users_last_24h: set[str] = set()
    promo_messages_by_sender: dict[str, Counter[str]] = defaultdict(Counter)

    for message in messages:
        normalized_text = _normalize_text(message.text or "")
        sent_at = message.sent_at.replace(tzinfo=None) if message.sent_at else None
        sender_id = str(message.sender_id) if message.sender_id is not None else None

        if sent_at and (metrics.last_message_at is None or sent_at > metrics.last_message_at):
            metrics.last_message_at = sent_at

        if sent_at and sent_at >= day_cutoff:
            metrics.messages_last_24h += 1
            if sender_id:
                unique_users_last_24h.add(sender_id)

        if sent_at and sent_at >= recent_cutoff:
            metrics.recent_messages_6h += 1

        if not normalized_text:
            continue

        if _contains_any(normalized_text, BUYER_INTENT_KEYWORDS):
            metrics.buyer_signal_count += 1
        if _contains_any(normalized_text, COMPETITOR_PAIN_SIGNALS):
            metrics.pain_signal_count += 1
        if _contains_any(normalized_text, SELLER_PROMOTION_KEYWORDS):
            metrics.seller_signal_count += 1
            if sender_id:
                promo_messages_by_sender[sender_id][normalized_text] += 1
        if "?" in normalized_text:
            metrics.question_count += 1
        if message.is_reply:
            metrics.reply_count += 1
        if URL_PATTERN.search(normalized_text):
            metrics.link_count += 1

    metrics.unique_users_last_24h = len(unique_users_last_24h)
    metrics.duplicate_promo_count = sum(
        count - 1
        for sender_texts in promo_messages_by_sender.values()
        for count in sender_texts.values()
        if count > 1
    )
    return metrics


def score_group_candidate(
    *,
    name: str,
    description: str | None,
    members_count: int,
    metrics: GroupActivityMetrics,
    ai_intent_scores: dict[str, float] | None = None,
    is_megagroup: bool,
    is_broadcast: bool,
    is_scam: bool,
    is_fake: bool,
    is_restricted: bool,
    request_needed: bool = False,
    join_request_enabled: bool = False,
    slowmode_seconds: int | None = None,
    now: datetime | None = None,
) -> GroupQualityDecision:
    now = now or datetime.utcnow()
    thresholds = GROUP_QUALITY_THRESHOLDS
    reasons: list[str] = []

    seller_share = metrics.seller_density
    buyer_share = metrics.buyer_density
    if ai_intent_scores:
        seller_share = max(seller_share, float(ai_intent_scores.get("SELLER_PROMOTION", 0.0) or 0.0))
        buyer_share = max(buyer_share, float(ai_intent_scores.get("BUYER_INTENT", 0.0) or 0.0))

    audience_text = f"{name} {description or ''}".lower()
    audience_fit_hits = sum(1 for keyword in BUYER_AUDIENCE_KEYWORDS if keyword in audience_text)

    if is_scam or is_fake or is_restricted:
        reasons.append("group is marked unsafe or restricted")
        return GroupQualityDecision(0, "REJECTED", False, "UNSAFE", reasons, seller_share, buyer_share, metrics.conversation_ratio)

    if is_broadcast or not is_megagroup:
        reasons.append("group is not an interactive megagroup")
        return GroupQualityDecision(0, "REJECTED", False, "BROADCAST", reasons, seller_share, buyer_share, metrics.conversation_ratio)

    if request_needed or join_request_enabled:
        reasons.append("group requires manual approval before entry")

    if members_count < thresholds["min_members"]:
        reasons.append(f"member count too low ({members_count})")

    if metrics.messages_last_24h < thresholds["min_messages_last_24h"]:
        reasons.append(f"not enough activity in last 24h ({metrics.messages_last_24h})")

    if metrics.unique_users_last_24h < thresholds["min_unique_users_last_24h"]:
        reasons.append(f"too few unique users in last 24h ({metrics.unique_users_last_24h})")

    if metrics.recent_messages_6h < thresholds["min_recent_messages_6h"]:
        reasons.append(f"too little recent activity in last 6h ({metrics.recent_messages_6h})")

    if metrics.last_message_at is None:
        reasons.append("no usable recent message history")
    else:
        last_message_age = now - metrics.last_message_at
        if last_message_age > timedelta(hours=thresholds["freshness_window_hours"]):
            reasons.append(f"last message is stale ({int(last_message_age.total_seconds() // 3600)}h old)")

    if seller_share >= thresholds["max_seller_density"]:
        reasons.append(f"seller density too high ({seller_share:.1%})")

    if metrics.duplicate_promo_ratio >= thresholds["max_duplicate_promo_ratio"]:
        reasons.append(f"duplicate promotion ratio too high ({metrics.duplicate_promo_ratio:.1%})")

    buyer_demand_score = max(buyer_share, metrics.pain_density + (metrics.question_ratio * 0.5))
    if buyer_demand_score < thresholds["min_buyer_signal_ratio"]:
        reasons.append(f"buyer demand too weak ({buyer_demand_score:.1%})")

    if metrics.conversation_ratio < thresholds["min_conversation_ratio"]:
        reasons.append(f"conversation ratio too low ({metrics.conversation_ratio:.1%})")

    activity_score = min(metrics.messages_last_24h / 120, 1.0) * 100
    engagement_score = min(metrics.unique_users_last_24h / 40, 1.0) * 100
    freshness_score = 0.0
    if metrics.last_message_at:
        freshness_hours = max(0.0, (now - metrics.last_message_at).total_seconds() / 3600)
        freshness_score = max(0.0, 100 - (freshness_hours * 6))
    demand_score = min(buyer_demand_score / 0.20, 1.0) * 100
    conversation_score = min(metrics.conversation_ratio / 0.15, 1.0) * 100
    member_score = min(members_count / 4000, 1.0) * 100
    audience_fit_score = min(audience_fit_hits / 3, 1.0) * 100

    score = (
        activity_score * 0.22
        + engagement_score * 0.18
        + demand_score * 0.24
        + conversation_score * 0.14
        + freshness_score * 0.12
        + member_score * 0.05
        + audience_fit_score * 0.05
    )

    seller_penalty = min(45.0, seller_share * 200)
    duplicate_penalty = min(20.0, metrics.duplicate_promo_ratio * 300)
    approval_penalty = 8.0 if (request_needed or join_request_enabled) else 0.0
    slowmode_penalty = 5.0 if slowmode_seconds and slowmode_seconds > 600 else 0.0
    final_score = max(0, round(score - seller_penalty - duplicate_penalty - approval_penalty - slowmode_penalty))

    if reasons:
        market_type = "SELLER HUB" if seller_share >= thresholds["max_seller_density"] else "LOW SIGNAL"
        status = "PENDING_APPROVAL" if (request_needed or join_request_enabled) and final_score >= thresholds["approval_score"] else "REJECTED"
        return GroupQualityDecision(final_score, status, False, market_type, reasons, seller_share, buyer_share, metrics.conversation_ratio)

    market_type = "BUYER COMMUNITY" if buyer_demand_score >= 0.10 else "DISCUSSION GROUP"
    if final_score >= thresholds["approval_score"]:
        status = "APPROVED"
        eligible = True
    elif final_score >= thresholds["watchlist_score"]:
        status = "WATCHLIST"
        eligible = False
    else:
        status = "REJECTED"
        eligible = False

    return GroupQualityDecision(final_score, status, eligible, market_type, reasons, seller_share, buyer_share, metrics.conversation_ratio)
