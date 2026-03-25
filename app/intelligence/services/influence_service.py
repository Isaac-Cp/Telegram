import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from app.db.session import SessionLocal
from app.models.message import Message
from app.models.user import User
from app.intelligence.models.influence_models import InfluenceProfile

logger = logging.getLogger(__name__)

class InfluenceEngine:
    """
    MODULE 1 - COMMUNITY INFLUENCE GRAPH ENGINE
    Identify influential users inside Telegram communities.
    """

    def update_influence_score(self, user_id: str, group_id: str):
        """
        Calculate and update the influence_score for a user in a specific group.
        STEP 3 & 4: Calculate metrics and compute influence_score.
        """
        with SessionLocal() as db:
            # Check if user and group exist (implicitly via foreign keys)
            
            # 1. messages_sent_last_24h
            day_ago = datetime.utcnow() - timedelta(hours=24)
            messages_sent = db.query(func.count(Message.id)).filter(
                and_(
                    Message.telegram_user_id == user_id,
                    Message.sent_at >= day_ago
                )
            ).scalar() or 0

            # 2. replies_received
            # Assuming we have reply_to_message_id in Message model
            # We need to find messages that are replies to messages sent by this user
            replies_received = db.query(func.count(Message.id)).filter(
                Message.reply_to_message_id.in_(
                    select(Message.telegram_message_id).where(Message.telegram_user_id == user_id)
                )
            ).scalar() or 0

            # 3. mentions_received (Placeholder for now as mention extraction isn't fully implemented)
            mentions = 0 
            
            # 4. threads_started
            # A thread is started if a message has replies but is not itself a reply
            threads_started = db.query(func.count(Message.id)).filter(
                and_(
                    Message.telegram_user_id == user_id,
                    Message.reply_to_message_id == None
                )
            ).scalar() or 0

            # STEP 4: INFLUENCE SCORE calculation
            # influence_score = (messages_sent * 0.3) + (replies_received * 0.4) + (mentions * 0.2) + (threads_started * 0.1)
            # Normalizing slightly to a 0-100 scale for classification
            score = (messages_sent * 3) + (replies_received * 4) + (mentions * 2) + (threads_started * 1)
            score = min(100.0, float(score))

            # STEP 5: INFLUENCE CLASSIFICATION
            if score > 80:
                level = "community_leader"
            elif score > 50:
                level = "power_user"
            else:
                level = "regular_member"

            # STEP 6: DATABASE UPDATE
            profile = db.execute(
                select(InfluenceProfile).where(
                    and_(
                        InfluenceProfile.user_id == user_id,
                        InfluenceProfile.group_id == group_id
                    )
                )
            ).scalar_one_or_none()

            if not profile:
                profile = InfluenceProfile(user_id=user_id, group_id=group_id)
                db.add(profile)

            profile.influence_score = score
            profile.influence_level = level
            profile.messages_sent_24h = messages_sent
            profile.replies_received = replies_received
            profile.mentions_received = mentions
            profile.threads_started = threads_started
            profile.last_updated = datetime.utcnow()

            db.commit()
            
            # STEP 7: LOGGING
            logger.info(f"[SLIE Influence Engine] influence score updated for user {user_id} in group {group_id}: {score} ({level})")
            return profile

influence_engine = InfluenceEngine()
