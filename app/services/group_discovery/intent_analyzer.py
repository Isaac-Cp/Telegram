import logging
import json
from typing import Dict
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)
ai_service = AIService()

class GroupIntentAnalyzer:
    """
    Advanced AI Filter to classify group message intent.
    Categorizes group atmosphere into BUYER_INTENT, SELLER_PROMOTION, or GENERAL_CHAT.
    """

    async def classify_group_intent(self, messages: list[str]) -> Dict[str, float]:
        """
        Analyze a batch of messages to determine the group's primary intent distribution.
        """
        if not messages:
            return {"BUYER_INTENT": 0.0, "SELLER_PROMOTION": 0.0, "GENERAL_CHAT": 1.0}

        # Sample messages to stay within token limits but get a good representative set
        sample_text = "\n---\n".join(messages[:50])
        
        prompt = f"""
        Analyze the following batch of Telegram messages from a single group.
        Classify the overall group activity into three categories:
        1. BUYER_INTENT: Users asking for help, recommendations, reporting problems, or looking to buy.
        2. SELLER_PROMOTION: Messages promoting services, trials, panels, resellers, or pricing.
        3. GENERAL_CHAT: Off-topic discussion, social chat, or technical talk not related to buying/selling.

        Return a JSON object with the percentage (0.0 to 1.0) for each category.
        The sum of all three must be 1.0.

        Messages:
        {sample_text}

        Example Output:
        {{
            "BUYER_INTENT": 0.35,
            "SELLER_PROMOTION": 0.10,
            "GENERAL_CHAT": 0.55
        }}
        """

        try:
            response = await ai_service.chat_completion(
                prompt=prompt,
                system_prompt="You are an expert market analyst specializing in Telegram community classification.",
                response_format="json_object"
            )
            
            if response:
                result = json.loads(response)
                logger.info(f"[AI Group Filter] Intent classification: {result}")
                return result
        except Exception as e:
            logger.error(f"[AI Group Filter] Intent classification failed: {e}")
            
        # KEYWORD FALLBACK (Module 2 Safety)
        logger.warning("[AI Group Filter] Falling back to keyword-based intent classification.")
        from app.services.group_discovery.discovery_config import BUYER_INTENT_KEYWORDS, SELLER_PROMOTION_KEYWORDS
        
        buyer_count = 0
        seller_count = 0
        total_sample = len(messages[:100])
        
        for msg in messages[:100]:
            text = msg.lower()
            if any(kw in text for kw in BUYER_INTENT_KEYWORDS):
                buyer_count += 1
            if any(kw in text for kw in SELLER_PROMOTION_KEYWORDS):
                seller_count += 1
        
        if total_sample > 0:
            buyer_p = buyer_count / total_sample
            seller_p = seller_count / total_sample
            general_p = max(0, 1.0 - buyer_p - seller_p)
            return {
                "BUYER_INTENT": buyer_p,
                "SELLER_PROMOTION": seller_p,
                "GENERAL_CHAT": general_p
            }
            
        return {"BUYER_INTENT": 0.0, "SELLER_PROMOTION": 0.0, "GENERAL_CHAT": 1.0}

group_intent_analyzer = GroupIntentAnalyzer()
