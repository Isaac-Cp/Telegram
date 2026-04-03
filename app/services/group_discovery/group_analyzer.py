import logging
from datetime import datetime, timedelta
from typing import Optional, List
from telethon import functions, errors
from telethon.tl.types import Channel, Chat, ChannelFull

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.seller_detector import seller_detector
from app.services.group_discovery.intent_analyzer import group_intent_analyzer

from app.services.group_discovery.discovery_config import SELLER_PROMOTION_KEYWORDS, COMPETITOR_PAIN_SIGNALS, BUYER_INTENT_KEYWORDS

logger = logging.getLogger(__name__)

async def collect_group_metadata(client, group: Group):
    """
    STEP 1 — GROUP METADATA ANALYSIS (Module 2 Elite)
    Fetch metadata using Telethon and perform initial rejection checks.
    """
    logger.info(f"[SLIE Group Filter] Fetching metadata for group: {group.name}")
    
    try:
        # Resolve target group/channel
        target = group.username if group.username else group.invite_link
        if not target:
            logger.warning(f"[SLIE Group Filter] Group {group.id} has no username or invite link. Skipping.")
            return False

        # Get full channel info
        full_channel = await client(functions.channels.GetFullChannelRequest(channel=target))
        
        # STEP 1: Participants Count Check (Reject if < 20 - Lowered for initial testing)
        participants_count = full_channel.full_chat.participants_count
        if participants_count < 20:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Small group ({participants_count} members)")
            group.status = "REJECTED"
            return False

        # STEP 3: ADMIN ONLY DETECTION (Check permissions)
        # Handle attribute differences between ChannelFull and ChatFull
        permissions = getattr(full_channel.full_chat, 'default_banned_rights', None)
        if permissions and permissions.send_messages:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Admin-only broadcast")
            group.status = "REJECTED"
            return False

        # Update group attributes
        group.telegram_id = full_channel.full_chat.id
        group.name = full_channel.chats[0].title
        group.username = getattr(full_channel.chats[0], 'username', None)
        group.members_count = participants_count
        group.last_scanned = datetime.utcnow()
        
        return True
            
    except errors.ChannelPrivateError:
        logger.warning(f"[SLIE Group Filter] Group {group.name} is private and inaccessible.")
        group.status = "REJECTED"
        return False
    except Exception as e:
        logger.error(f"[SLIE Group Filter] Error collecting metadata for group {group.name}: {e}")
        return False

async def analyze_group_activity(client, group: Group):
    """
    STEP 2, 4, 5, 6 — MESSAGE & DISCUSSION ANALYSIS (Module 2 Elite)
    Analyze last 200 messages for activity, promotions, and discussion quality.
    """
    logger.info(f"[SLIE Group Filter] Analyzing activity for group: {group.name}")
    
    try:
        target = group.username if group.username else group.invite_link
        if not target:
            return False

        now = datetime.utcnow()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # PARAMETERS
        messages_last_24h = 0
        unique_users_last_24h = set()
        promotion_count = 0
        discussion_count = 0
        user_message_hashes = {} # For Spam Detection (Check 6)
        
        # Promotion Keyword Dictionary (Step 4)
        from app.services.group_discovery.discovery_config import SELLER_PROMOTION_KEYWORDS, BUYER_INTENT_KEYWORDS
        PROMO_KEYWORDS = SELLER_PROMOTION_KEYWORDS
        # Discussion Quality Keywords (Step 5)
        DISCUSSION_KEYWORDS = BUYER_INTENT_KEYWORDS

        # Scan last 200 messages
        total_messages = 0
        all_messages = []
        async for message in client.iter_messages(target, limit=200):
            total_messages += 1
            msg_text = (message.message or "").lower()
            all_messages.append(msg_text)
            
            # Check if within last 24h
            if message.date and message.date.replace(tzinfo=None) >= twenty_four_hours_ago:
                messages_last_24h += 1
                if message.from_id:
                    unique_users_last_24h.add(str(message.from_id))
            
            # STEP 4: PROMOTION DETECTION
            is_promo = False
            if any(kw in msg_text for kw in PROMO_KEYWORDS):
                promotion_count += 1
                is_promo = True

            # STEP 5: DISCUSSION QUALITY ANALYSIS
            if any(kw in msg_text for kw in DISCUSSION_KEYWORDS):
                discussion_count += 1

            # STEP 6: SPAM DETECTION (Identical messages)
            if is_promo and message.from_id:
                u_id = str(message.from_id)
                if u_id not in user_message_hashes:
                    user_message_hashes[u_id] = set()
                
                msg_hash = hash(msg_text)
                if msg_hash in user_message_hashes[u_id]:
                    logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Spam patterns detected")
                    group.status = "REJECTED"
                    return False
                user_message_hashes[u_id].add(msg_hash)
        
        # --- AI INTENT ANALYSIS (Advanced Fix) ---
        intent_scores = await group_intent_analyzer.classify_group_intent(all_messages)
        buyer_intent_score = intent_scores.get("BUYER_INTENT", 0.0)
        
        # Recommendation: Join only if BUYER_INTENT > 5% (Temporary for demonstration)
        if buyer_intent_score < 0.05:
            # Check if it has at least some signals or is a discussion group
            discussion_count = sum(1 for msg in all_messages if any(kw in msg for kw in DISCUSSION_KEYWORDS))
            if discussion_count < 2:
                logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Very low buyer signals ({buyer_intent_score:.2%}, Signals: {discussion_count})")
                group.status = "REJECTED"
                return False
            else:
                logger.info(f"[SLIE Group Filter] Group {group.name} ACCEPTED - Low intent but has some signals ({discussion_count})")
                buyer_intent_score = 0.10 # Boost for acceptance

        # --- REJECTION RULES ---

        # STEP 2: ACTIVITY ANALYSIS
        if messages_last_24h < 15:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Low activity ({messages_last_24h} msgs/24h)")
            group.status = "REJECTED"
            return False
            
        if len(unique_users_last_24h) < 7:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Low engagement ({len(unique_users_last_24h)} unique users)")
            group.status = "REJECTED"
            return False

        # STEP 4: SELLER HUB FILTER (> 15% promotions)
        promotion_ratio = (promotion_count / total_messages) if total_messages > 0 else 0
        group.seller_density = promotion_ratio
        if promotion_ratio > 0.15:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Seller Hub ({promotion_ratio:.2%})")
            group.status = "REJECTED"
            group.saturation_status = "SELLER HUB"
            return False

        # Update metrics for scoring
        group.messages_last_24h = messages_last_24h
        group.unique_users_last_24h = len(unique_users_last_24h)
        
        # STEP 2: Message Frequency Check (Reject if < 5 per day - Master Prompt Step 5)
        if messages_last_24h < 5:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Low activity ({messages_last_24h} msgs/24h)")
            group.status = "REJECTED"
            return False

        # Module 3: Advanced Seller Density Detection
        seller_ratio, market_type = await seller_detector.analyze_market_saturation(group.id)
        
        # Master Prompt Step 6: Only join DISCUSSION_GROUP communities
        if market_type != "DISCUSSION GROUP":
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Not a discussion group (Type: {market_type}, Ratio: {seller_ratio:.2%})")
            group.status = "REJECTED"
            return False
        
        if market_type == "SELLER HUB":
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Seller Hub detected ({seller_ratio:.2%})")
            group.status = "REJECTED"
            return False
        
        # Discussion Ratio (Step 5)
        discussion_ratio = (discussion_count / total_messages) if total_messages > 0 else 0
        group.discussion_signal = discussion_count # Store for scoring engine
        
        logger.info(f"[SLIE Group Filter] Analysis complete: {group.name} (Market: {market_type}, Discussion: {discussion_ratio:.2%})")
        return True
            
    except Exception as e:
        logger.error(f"[SLIE Group Filter] Error analyzing activity for group {group.name}: {e}")
        return False
