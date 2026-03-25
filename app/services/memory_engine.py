import logging
import json
from datetime import datetime
from sqlalchemy import select, desc, func
from app.db.session import SessionLocal
from app.models.user import User
from app.models.conversation_memory import UnifiedConversation, ConversationSummary
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class ConversationMemoryEngine:
    """
    Elite Module 15: Conversation Memory Engine.
    Maintain persistent conversation history for each lead across all Telegram groups.
    """

    def log_message_interaction(self, user_id: str, group_id: str | None, message_text: str, message_type: str):
        """
        STEP 1 — STORE MESSAGES
        Store every conversation event.
        message_type: group_message, public_reply, dm_message, user_reply
        """
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                logger.warning(f"MemoryEngine: User {user_id} not found.")
                return

            # Store the conversation event
            conv = UnifiedConversation(
                user_id=user_id,
                group_id=group_id,
                message_text=message_text,
                message_type=message_type,
                timestamp=datetime.utcnow()
            )
            db.add(conv)

            # Update global user metrics
            user.last_seen = datetime.utcnow()
            user.message_frequency += 1
            
            db.commit()
            logger.info(f"SLIE Memory Engine: log_message_interaction - User: {user_id}, Type: {message_type}")

            # STEP 4 — MEMORY SUMMARIZATION (Check if summary needed)
            message_count = db.query(func.count(UnifiedConversation.id)).filter(
                UnifiedConversation.user_id == user_id
            ).scalar()
            
            # Check if we should summarize (Module 15: every 100 messages)
            summary = db.execute(
                select(ConversationSummary).where(ConversationSummary.user_id == user_id)
            ).scalar_one_or_none()
            
            last_summary_count = summary.message_count_at_last_summary if summary else 0
            if message_count >= 100 and (message_count - last_summary_count) >= 100:
                import asyncio
                asyncio.create_task(self.generate_conversation_summary(user_id))

    def get_recent_history(self, user_id: str, limit: int = 10):
        """
        STEP 2 — CONTEXT RETRIEVAL
        Retrieve last N conversation entries.
        """
        with SessionLocal() as db:
            recent_convs = db.execute(
                select(UnifiedConversation)
                .where(UnifiedConversation.user_id == user_id)
                .order_by(desc(UnifiedConversation.timestamp))
                .limit(limit)
            ).scalars().all()
            return list(recent_convs)

    async def generate_conversation_summary(self, user_id: str):
        """
        STEP 4 — MEMORY SUMMARIZATION
        Analyze past conversation messages and produce a summary and metadata.
        """
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                return

            # Get all history or at least a large chunk for summary
            all_history = db.execute(
                select(UnifiedConversation)
                .where(UnifiedConversation.user_id == user_id)
                .order_by(UnifiedConversation.timestamp.asc())
            ).scalars().all()
            
            message_count = len(all_history)
            history_text = "\n".join([f"{c.message_type}: {c.message_text}" for c in all_history])
            
            prompt = f"""
            Summarize the following conversation history for an IPTV lead.
            The summary should be concise but include:
            1. Technical issues faced (e.g., buffering, setup).
            2. Product interest (e.g., trial, reseller, premium).
            3. Sentiment and engagement level.

            Return JSON format:
            {{
                "summary": "Concise summary of interaction history...",
                "problem_type": "buffering/setup/reseller/etc",
                "interest_level": "low/medium/high",
                "stage": "new/engaged/follow_up/converted"
            }}

            HISTORY:
            {history_text}
            """

            try:
                content = await ai_service.chat_completion(prompt=prompt, response_format="json_object")
                data = json.loads(content) if content else {}
                
                summary = db.execute(
                    select(ConversationSummary).where(ConversationSummary.user_id == user_id)
                ).scalar_one_or_none()
                
                if not summary:
                    summary = ConversationSummary(user_id=user_id)
                    db.add(summary)
                
                summary.summary_text = data.get("summary")
                summary.problem_type = data.get("problem_type")
                summary.interest_level = data.get("interest_level")
                summary.conversation_stage = data.get("stage", "new")
                summary.message_count_at_last_summary = message_count
                
                # Update last problem detection
                if "buffering" in (summary.problem_type or "").lower():
                    summary.last_problem_detected = datetime.utcnow()

                db.commit()
                logger.info(f"SLIE Memory Engine: generate_conversation_summary - User: {user_id}")
            except Exception as e:
                logger.error(f"Error generating conversation summary: {e}")

    def get_ai_context(self, user_id: str) -> str:
        """
        STEP 3 — CONTEXTUAL RESPONSE
        Generates a context string for AI injection using memory.
        """
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                return ""
            
            summary = db.execute(
                select(ConversationSummary).where(ConversationSummary.user_id == user_id)
            ).scalar_one_or_none()
            
            recent_history = self.get_recent_history(user_id, limit=10)
            
            context = "--- CONVERSATION MEMORY ---\n"
            
            if summary and summary.summary_text:
                context += f"Historical Summary: {summary.summary_text}\n"
                context += f"Last Problem: {summary.problem_type}\n"
                if summary.last_problem_detected:
                    context += f"Problem Date: {summary.last_problem_detected.strftime('%Y-%m-%d')}\n"
            
            if recent_history:
                context += "Recent Messages (last 10):\n"
                for msg in reversed(recent_history):
                    context += f"- {msg.message_type}: {msg.message_text}\n"
            
            context += "---------------------------\n"
            return context

memory_engine = ConversationMemoryEngine()
