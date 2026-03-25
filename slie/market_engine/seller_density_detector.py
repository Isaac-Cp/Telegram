import logging
from typing import Tuple, List
from sqlalchemy import select, desc, update
from slie.core.database import AsyncSessionLocal
from slie.models.group_models import Group, GroupMarketAnalysis
from slie.models.conversation_models import Message

logger = logging.getLogger(__name__)

class SellerDensityDetector:
    """
    STEP 6: SELLER DENSITY DETECTOR
    Purpose: Avoid seller hubs.
    Process last 200 messages in group. Detect promotional keywords.
    """
    PROMOTIONAL_KEYWORDS = [
        "cheap iptv", "buy iptv", "trial available", "reseller panel",
        "xtream codes", "m3u list", "best price", "dm for info",
        "whatsapp me", "high quality iptv", "anti-freeze", "no buffering"
    ]

    async def analyze_market_saturation(self, telegram_group_id: int) -> Tuple[float, str]:
        """
        Scan last 200 messages and classify market type.
        seller_ratio = promotional_messages / total_messages
        """
        async with AsyncSessionLocal() as db:
            # 1. Fetch group from DB
            stmt = select(Group).where(Group.telegram_id == telegram_group_id)
            result = await db.execute(stmt)
            group = result.scalar_one_or_none()
            if not group:
                logger.error(f"[SLIE Market Engine] Group {telegram_group_id} not found in database.")
                return 0.0, "DISCUSSION_GROUP"

            # 2. Fetch last 200 messages from group
            stmt = select(Message.body).where(
                Message.telegram_group_id == telegram_group_id
            ).order_by(desc(Message.sent_at)).limit(200)
            
            result = await db.execute(stmt)
            messages = result.scalars().all()
            
            total_messages = len(messages)
            if total_messages == 0:
                logger.info(f"[SLIE Market Engine] No messages found for group {group.name} to analyze.")
                return 0.0, "DISCUSSION_GROUP"

            # 3. Detect promotional messages
            promo_count = 0
            for msg_body in messages:
                text = msg_body.lower()
                if any(keyword in text for keyword in self.PROMOTIONAL_KEYWORDS):
                    promo_count += 1
            
            # 4. Compute seller_ratio
            seller_ratio = promo_count / total_messages
            
            # 5. Classification (Step 6)
            if seller_ratio > 0.4:
                market_type = "SELLER_HUB"
            elif 0.2 <= seller_ratio <= 0.4:
                market_type = "MIXED_GROUP"
            else:
                market_type = "DISCUSSION_GROUP"
            
            # 6. Store results in database
            group.seller_density = seller_ratio
            group.saturation_status = market_type
            
            # Update or create GroupMarketAnalysis
            analysis_stmt = select(GroupMarketAnalysis).where(GroupMarketAnalysis.group_id == group.id)
            analysis_result = await db.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
            
            if analysis:
                analysis.seller_ratio = seller_ratio
                analysis.market_type = market_type
                analysis.promotional_msg_count = promo_count
                analysis.total_msg_analyzed = total_messages
            else:
                new_analysis = GroupMarketAnalysis(
                    group_id=group.id,
                    seller_ratio=seller_ratio,
                    market_type=market_type,
                    promotional_msg_count=promo_count,
                    total_msg_analyzed=total_messages
                )
                db.add(new_analysis)
            
            await db.commit()
            
            # Logging (Requirement)
            if market_type == "SELLER_HUB":
                logger.warning(f"[SLIE Market Engine] seller hub detected: {group.name} (Ratio: {seller_ratio:.2f})")
            else:
                logger.info(f"[SLIE Market Engine] Group analysis complete: {group.name} is {market_type} (Ratio: {seller_ratio:.2f})")
            
            return seller_ratio, market_type

seller_detector = SellerDensityDetector()
