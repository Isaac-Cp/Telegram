import logging
from datetime import datetime

from app.models.group import Group
from app.services.group_discovery.discovery_config import GROUP_QUALITY_THRESHOLDS

logger = logging.getLogger(__name__)


def calculate_authority_score(group: Group):
    """
    Convert sampled group-quality signals into a stable authority score that can
    be used for prioritizing joins.
    """
    thresholds = GROUP_QUALITY_THRESHOLDS

    if group.status in {"REJECTED", "PENDING_APPROVAL"} or group.saturation_status == "SELLER HUB":
        group.status = "REJECTED"
        group.eligible_for_join = False
        group.authority_score = int(group.quality_score or 0)
        logger.info("[SLIE Group Filter] Group REJECTED - Seller Hub or hard filter: %s", group.name)
        return group.authority_score

    freshness_score = 0.0
    if group.last_message_timestamp:
        freshness_hours = max(
            0.0,
            (datetime.utcnow().replace(tzinfo=None) - group.last_message_timestamp.replace(tzinfo=None)).total_seconds() / 3600,
        )
        freshness_score = max(0.0, 100 - (freshness_hours * 6))

    member_score = min((group.members_count or 0) / 4000 * 100, 100)
    activity_score = min((group.messages_last_24h or 0) / 120 * 100, 100)
    discussion_score = min((group.discussion_signal or 0) / 25 * 100, 100)
    users_score = min((group.unique_users_last_24h or 0) / 40 * 100, 100)
    quality_baseline = group.quality_score or 0
    market_bonus = 10 if group.saturation_status == "BUYER COMMUNITY" else 4
    seller_penalty = min(55.0, (group.seller_density or 0.0) * 220)

    authority_score = (
        quality_baseline * 0.35
        + activity_score * 0.20
        + discussion_score * 0.20
        + users_score * 0.15
        + freshness_score * 0.05
        + member_score * 0.05
        + market_bonus
        - seller_penalty
    )
    authority_score = max(0, int(round(authority_score)))

    group.authority_score = authority_score
    group.quality_score = max(int(quality_baseline), authority_score)

    if group.quality_score >= thresholds["approval_score"] and authority_score >= thresholds["approval_score"]:
        group.status = "APPROVED"
        group.eligible_for_join = True
        logger.info("[SLIE Group Filter] Group APPROVED (Authority=%s, Quality=%s) - %s", authority_score, group.quality_score, group.name)
    elif group.quality_score >= thresholds["watchlist_score"] and authority_score >= thresholds["watchlist_score"]:
        group.status = "WATCHLIST"
        group.eligible_for_join = False
        logger.info("[SLIE Group Filter] Group WATCHLIST (Authority=%s, Quality=%s) - %s", authority_score, group.quality_score, group.name)
    else:
        group.status = "REJECTED"
        group.eligible_for_join = False
        logger.info("[SLIE Group Filter] Group REJECTED (Authority=%s, Quality=%s) - %s", authority_score, group.quality_score, group.name)

    return authority_score
