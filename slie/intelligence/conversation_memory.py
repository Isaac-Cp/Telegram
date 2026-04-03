import logging
from datetime import datetime
from sqlalchemy import select, and_
from slie.core.database import AsyncSessionLocal
from slie.models.conversation_models import Conversation

logger = logging.getLogger(__name__)

class ConversationMemoryEngine:
    """
    STEP 11: CONVERSATION MEMORY ENGINE
    Store previous interactions to ensure follow-up messages reference previous conversations.
    """

    async def log_interaction(self, user_id: str, group_id: str | None, message_text: str, role: str = "user"):
        """
        Store interaction in the conversations table.
        """
        async with AsyncSessionLocal() as db:
            stmt = select(Conversation).where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.group_id == group_id
                )
            )
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()

            if not conv:
                conv = Conversation(
                    user_id=user_id, 
                    group_id=group_id, 
                    messages="", 
                    interaction_history={"events": []}
                )
                db.add(conv)

            # Append message to interaction history
            history = conv.interaction_history or {"events": []}
            events = history.get("events", [])
            events.append({
                "role": role,
                "text": message_text,
                "timestamp": datetime.utcnow().isoformat()
            })
            history["events"] = events
            conv.interaction_history = history
            
            # Concatenate message text for memory
            conv.messages = (conv.messages or "") + f"\n{role}: {message_text}"
            conv.last_interaction = datetime.utcnow()
            
            await db.commit()
            logger.info(f"[SLIE Intelligence] Interaction logged for user {user_id}")

    async def get_interaction_history(self, user_id: str, group_id: str | None = None) -> str:
        """
        Retrieve interaction history for contextual response.
        """
        async with AsyncSessionLocal() as db:
            stmt = select(Conversation).where(Conversation.user_id == user_id)
            if group_id:
                stmt = stmt.where(Conversation.group_id == group_id)
            
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()
            return conv.messages if conv else ""

memory_engine = ConversationMemoryEngine()
