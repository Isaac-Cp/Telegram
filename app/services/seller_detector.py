import logging
from datetime import datetime, timedelta
from typing import Tuple, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.group import Group
from app.models.message import Message

logger = logging.getLogger(__name__)

# Module 3 Signals (Seller/Reseller focused)
PROMOTIONAL_PHRASES = [
    "reseller", "panel", "trial", "wholesale", "server", "credits", "restream",
    "buy iptv", "cheap iptv", "contact for price", "dm for price",
    "reseller panel", "iptv subscription", "panel available", "trial available",
    "iptv service", "best server", "no buffering server"
]

# Buyer/User signals (Module 2 Elite)
BUYER_SIGNALS = [
    "best iptv", "cheap iptv", "iptv problem", "iptv buffering", 
    "iptv recommendation", "iptv app", "iptv help", "iptv channels", 
    "iptv sports", "iptv subscription", "firestick", "android tv", 
    "smart tv", "mag box", "tivimate", "ott navigator", "kodi", 
    "cord cutters", "any good iptv", "need provider", "recommend provider"
]

class SellerDensityDetector:
    """
    MODULE 3 — SELLER DENSITY DETECTOR
    Avoid joining or operating in oversaturated groups where many sellers are promoting IPTV services.
    """

    async def analyze_market_saturation(self, group_id: str) -> Tuple[float, str]:
        """
        Scan last 200 messages within the group and classify market type (Master Prompt Step 6).
        Also calculates a Buyer Density Score.
        """
        with SessionLocal() as db:
            from sqlalchemy import desc
            group = db.get(Group, group_id)
            if not group or not group.telegram_id:
                return 0.0, "DISCUSSION GROUP"

            # 1. Fetch last 200 messages from group (Master Prompt Step 6)
            messages = db.execute(
                select(Message.body).where(
                    Message.telegram_group_id == group.telegram_id
                ).order_by(desc(Message.sent_at)).limit(200)
            ).scalars().all()
            
            total_messages = len(messages)
            if total_messages == 0:
                return 0.0, "DISCUSSION GROUP"

            # 2. Identify signals
            promo_count = 0
            buyer_count = 0
            for msg in messages:
                text = msg.lower()
                # Seller signals
                if any(phrase in text for phrase in PROMOTIONAL_PHRASES):
                    promo_count += 1
                # Buyer signals
                if any(phrase in text for phrase in BUYER_SIGNALS):
                    buyer_count += 1
            
            # 3. Calculate Ratios
            seller_ratio = promo_count / total_messages
            buyer_ratio = buyer_count / total_messages
            
            # 4. Market Saturation Logic (Master Prompt Step 6)
            # Seller Density Filter: Skip if seller_keywords > 15% (User recommendation)
            if seller_ratio > 0.15:
                market_type = "SELLER HUB"
            elif buyer_ratio > 0.25:
                market_type = "BUYER COMMUNITY"
            elif seller_ratio >= 0.10:
                market_type = "MIXED GROUP"
            else:
                market_type = "DISCUSSION GROUP"
            
            # Update Group model
            group.seller_density = seller_ratio
            group.saturation_status = market_type
            # Use quality_score as a proxy for Buyer Density Score
            group.quality_score = int(buyer_ratio * 100)
            
            db.commit()
            
            # MODULE 6 — LOGGING (Master Prompt Step 6)
            if market_type == "SELLER HUB":
                logger.warning(f"[SLIE Market Engine] seller hub detected: {group.name} - Seller Density: {seller_ratio:.2%}")
            elif market_type == "BUYER COMMUNITY":
                logger.info(f"[SLIE Market Engine] Buyer community detected: {group.name} - Buyer Density: {buyer_ratio:.2%}")
            else:
                logger.info(f"[SLIE Market Engine] Group analyzed: {group.name} - Type: {market_type}")
            
            return seller_ratio, market_type

seller_detector = SellerDensityDetector()
