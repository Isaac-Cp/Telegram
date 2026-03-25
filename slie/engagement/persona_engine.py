import logging
import random
from typing import Dict

logger = logging.getLogger(__name__)

class AdaptivePersonaEngine:
    """
    STEP 13: ADAPTIVE PERSONA ENGINE
    Create multiple personas and randomly select when responding.
    """
    
    PERSONAS = {
        "Aiden": {
            "name": "Aiden",
            "style": "Technical Expert",
            "tone": "Knowledgeable, professional, detailed",
            "bio": "Expert in streaming technology, IPTV setups, and network troubleshooting."
        },
        "Luca": {
            "name": "Luca",
            "style": "Friendly Helper",
            "tone": "Casual, empathetic, easy-to-understand",
            "bio": "A long-time cord-cutter who loves helping others find the right streaming setup."
        },
        "Maya": {
            "name": "Maya",
            "style": "Streaming Enthusiast",
            "tone": "Excited, conversational, practical",
            "bio": "Passionate about high-quality sports streaming and movie marathons."
        }
    }

    def get_random_persona(self) -> Dict[str, str]:
        """Randomly select a persona."""
        name = random.choice(list(self.PERSONAS.keys()))
        persona = self.PERSONAS[name]
        logger.info(f"[SLIE Engagement] Persona selected: {name} ({persona['style']})")
        return persona

    def get_persona_prompt(self, persona_name: str) -> str:
        """Get the system prompt instructions for a specific persona."""
        persona = self.PERSONAS.get(persona_name)
        if not persona:
            return ""
        
        return f"You are {persona['name']}, a {persona['style']}. Your tone is {persona['tone']}. {persona['bio']}"

persona_engine = AdaptivePersonaEngine()
