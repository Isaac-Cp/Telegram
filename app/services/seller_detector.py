import logging
from datetime import datetime, timedelta
from typing import Tuple, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.group import Group
from app.models.message import Message

logger = logging.getLogger(__name__)

# Module 3 Signals
PROMOTIONAL_PHRASES = [
    "buy iptv", "cheap iptv", "trial available", "contact for price", 
    "reseller panel", "best iptv", "iptv subscription", "panel available"
]

class SellerDensityDetector:
    """
    MODULE 3 — SELLER DENSITY DETECTOR
    Avoid joining or operating in oversaturated groups where many sellers are promoting IPTV services.
    """

    async def analyze_market_saturation(self, group_id: str) -> Tuple[float, str]:
        """
        Scan last 200 messages within the group and classify market type (Master Prompt Step 6).
        """
        with SessionLocal() as db:
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

            # 2. Identify advertisement messages
            promo_count = 0
            for msg in messages:
                text = msg.lower()
                if any(phrase in text for phrase in PROMOTIONAL_PHRASES):
                    promo_count += 1
            
            # 3. Calculate Seller Ratio
            seller_ratio = promo_count / total_messages
            
            # 4. Market Saturation Logic (Master Prompt Step 6)
            if seller_ratio > 0.4:
                market_type = "SELLER HUB"
            elif seller_ratio >= 0.2:
                market_type = "MIXED GROUP"
            else:
                market_type = "DISCUSSION GROUP"
            
            # Update Group model
            group.seller_density = seller_ratio
            group.saturation_status = market_type
            
            db.commit()
            
            # MODULE 6 — LOGGING (Master Prompt Step 6)
            if market_type == "SELLER HUB":
                logger.warning(f"[SLIE Market Engine] seller hub detected: {group.name} - Density: {seller_ratio:.2%}")
            else:
                logger.info(f"[SLIE Market Engine] Group analyzed: {group.name} - Type: {market_type}")
            
            return seller_ratio, market_type

seller_detector = SellerDensityDetector()
