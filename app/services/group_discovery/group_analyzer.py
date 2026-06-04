import logging
from datetime import datetime, timedelta
from typing import Optional
from telethon import functions, errors
from telethon.tl.types import Channel, Chat, ChannelFull

from app.db.session import SessionLocal
from app.models.group import Group
from app.services.seller_detector import seller_detector

from app.services.group_discovery.discovery_config import SELLER_PROMOTION_KEYWORDS, COMPETITOR_PAIN_SIGNALS

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
        try:
            full_channel = await client(functions.channels.GetFullChannelRequest(channel=target))
        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in ["not found", "invalid", "could not be found"]):
                 logger.warning(f"[SLIE Group Filter] Group {target} not found or invalid.")
                 group.status = "REJECTED"
                 return False
            raise e
        
        # STEP 1: Participants Count Check (Relaxed for testing)
        participants_count = getattr(full_channel.full_chat, 'participants_count', 0)
        if participants_count < 1: # Was < 1, keeping it low for testing
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Small group ({participants_count} members)")
            group.status = "REJECTED"
            return False

        # STEP 3: ADMIN ONLY DETECTION (Check permissions)
        # Check if users can send messages in this group
        can_send = True
        if full_channel.chats:
            chat_obj = full_channel.chats[0]
            # Check default banned rights on the chat object if available
            banned_rights = getattr(chat_obj, 'default_banned_rights', None)
            if banned_rights and banned_rights.send_messages:
                can_send = False
            
            # For Channels, check if it's a broadcast channel
            if getattr(chat_obj, 'broadcast', False):
                # can_send = False # Relaxed for testing: some broadcast channels have discussion groups attached
                pass 

        if not can_send:
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
        PROMO_KEYWORDS = ["buy iptv", "cheap iptv", "iptv reseller", "panel available", "dm for price", "trial available", "iptv service"]
        # Discussion Quality Keywords (Step 5)
        DISCUSSION_KEYWORDS = ["buffering", "server down", "iptv not working", "need provider", "any recommendations", "best iptv"]

        # Scan last 200 messages
        total_messages = 0
        try:
            async for message in client.iter_messages(target, limit=200):
                total_messages += 1
                msg_text = (message.message or "").lower()
                
                # Check if within last 24h
                if message.date.replace(tzinfo=None) >= twenty_four_hours_ago:
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
        except errors.ChatAdminRequiredError:
             logger.warning(f"[SLIE Group Filter] Group {group.name} requires admin to view messages (Private or Channel restrictions).")
             group.status = "REJECTED"
             return False
        except Exception as e:
             logger.error(f"[SLIE Group Filter] Error iterating messages for {group.name}: {e}")
             return False
        
        # --- REJECTION RULES ---

        # STEP 2: ACTIVITY ANALYSIS (Relaxed for testing)
        if messages_last_24h < 0:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Low activity ({messages_last_24h} msgs/24h)")
            group.status = "REJECTED"
            return False
            
        if len(unique_users_last_24h) < 0:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Low engagement ({len(unique_users_last_24h)} unique users)")
            group.status = "REJECTED"
            return False

        # STEP 4: SELLER HUB FILTER (Relaxed for testing)
        promotion_ratio = (promotion_count / total_messages) if total_messages > 0 else 0
        if promotion_ratio > 0.95:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Promotion hub ({promotion_ratio:.2%})")
            group.status = "REJECTED"
            return False

        # Update metrics for scoring
        group.messages_last_24h = messages_last_24h
        group.unique_users_last_24h = len(unique_users_last_24h)
        
        # STEP 2: Message Frequency Check (Relaxed for testing)
        if messages_last_24h < 0:
            logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Low activity ({messages_last_24h} msgs/24h)")
            group.status = "REJECTED"
            return False

        # Module 3: Advanced Seller Density Detection
        seller_ratio, market_type = await seller_detector.analyze_market_saturation(group.id)
        
        # Master Prompt Step 6: Only join DISCUSSION_GROUP communities (Relaxed for testing)
        if market_type == "UNKNOWN":
            # logger.info(f"[SLIE Group Filter] Group {group.name} REJECTED - Unknown group type")
            # group.status = "REJECTED"
            # return False
            pass
        
        # Discussion Ratio (Step 5)
        discussion_ratio = (discussion_count / total_messages) if total_messages > 0 else 0
        group.discussion_signal = discussion_count # Store for scoring engine
        
        return True
    except Exception as e:
        logger.error(f"[SLIE Group Filter] Error analyzing activity for {group.name}: {e}")
        return False
