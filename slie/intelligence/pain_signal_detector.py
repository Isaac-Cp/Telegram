import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class PainSignalDetector:
    """
    STEP 8: PAIN SIGNAL DETECTOR
    Classify messages into categories:
    COMPLAINT, BUY_INTENT, TECH_DISCUSSION, GENERAL_CHAT.
    Assign intent score.
    """
    
    INTENT_MAP = {
        "BUY_INTENT": 90.0,
        "COMPLAINT": 70.0,
        "TECH_DISCUSSION": 40.0,
        "GENERAL_CHAT": 0.0
    }

    SIGNALS = {
        "BUY_INTENT": [
            "need iptv provider", "looking for better service", "recommend iptv",
            "want to buy", "any reliable provider", "how much is subscription",
            "best iptv for sports", "best iptv for movies", "trial?"
        ],
        "COMPLAINT": [
            "buffering", "server down", "lagging", "channels not working",
            "bad support", "no response from admin", "refund", "scam",
            "black screen", "freezing", "channels missing"
        ],
        "TECH_DISCUSSION": [
            "xtream codes", "m3u", "tivimate", "ott navigator",
            "firestick", "android box", "how to install", "configuration",
            "dns", "proxy", "vpn settings"
        ]
    }

    async def classify_message(self, text: str) -> Tuple[str, float]:
        """Classify message text and return category and intent score."""
        text = text.lower()
        
        # Check BUY_INTENT
        if any(signal in text for signal in self.SIGNALS["BUY_INTENT"]):
            return "BUY_INTENT", self.INTENT_MAP["BUY_INTENT"]
        
        # Check COMPLAINT
        if any(signal in text for signal in self.SIGNALS["COMPLAINT"]):
            return "COMPLAINT", self.INTENT_MAP["COMPLAINT"]
        
        # Check TECH_DISCUSSION
        if any(signal in text for signal in self.SIGNALS["TECH_DISCUSSION"]):
            return "TECH_DISCUSSION", self.INTENT_MAP["TECH_DISCUSSION"]
        
        return "GENERAL_CHAT", self.INTENT_MAP["GENERAL_CHAT"]

pain_detector = PainSignalDetector()
