import logging
from app.models.group import Group
from app.services.group_discovery.discovery_config import SCORING_THRESHOLDS

logger = logging.getLogger(__name__)

def calculate_authority_score(group: Group):
    """
    STEP 7: QUALITY SCORE CALCULATION (Module 2 Elite Upgrade)
    Compute a quality score for each group using the multi-factor weighted formula.
    
    FORMULA:
    quality_score = (member_score * 0.25) + (activity_score * 0.35) + (discussion_score * 0.25) + (unique_users_score * 0.15)
    """
    members = group.members_count or 0
    messages_24h = group.messages_last_24h or 0
    discussion_signal = group.discussion_signal or 0
    unique_users = group.unique_users_last_24h or 0
    
    # Normalize components to 0-100 scale for scoring
    # 1. Members (Normalize: 2000+ members = 100 score)
    member_score = min(members / 2000 * 100, 100)
    # 2. Activity (Normalize: 100+ messages/24h = 100 score)
    activity_score = min(messages_24h / 100 * 100, 100)
    # 3. Discussion Signal (Normalize: 10+ buyer signals = 100 score)
    discussion_score = min(discussion_signal / 10 * 100, 100)
    # 4. Unique Users (Normalize: 50+ users/24h = 100 score)
    users_score = min(unique_users / 50 * 100, 100)
    
    # Calculate weighted final score (Step 7)
    final_quality_score = (member_score * 0.25) + (activity_score * 0.35) + (discussion_score * 0.25) + (users_score * 0.15)
    
    group.authority_score = int(final_quality_score)
    group.quality_score = int(final_quality_score)
    
    # STEP 8: GROUP CLASSIFICATION
    if final_quality_score > 70:
        group.status = "APPROVED"
        group.eligible_for_join = True
        logger.info(f"[SLIE Group Filter] Group APPROVED (Score: {final_quality_score:.2f}) - {group.name}")
    elif final_quality_score >= 40:
        group.status = "MEDIUM"
        group.eligible_for_join = False
        logger.info(f"[SLIE Group Filter] Group analyzed (Score: {final_quality_score:.2f}) - {group.name}")
    else:
        group.status = "REJECTED"
        group.eligible_for_join = False
        logger.info(f"[SLIE Group Filter] Group REJECTED (Score: {final_quality_score:.2f}) - {group.name}")
        
    return final_quality_score
