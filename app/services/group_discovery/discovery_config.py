TARGET_KEYWORDS = [
    "iptv", # Broad keyword for discovery
    "best iptv",
    "cheap iptv",
    "iptv problem",
    "iptv buffering",
    "iptv recommendation",
    "iptv app",
    "iptv help",
    "iptv channels",
    "iptv sports",
    "iptv subscription",
    
    # Device communities
    "firestick",
    "android tv",
    "smart tv",
    "mag box",
    "tivimate",
    "ott navigator",
    "kodi",
    "cord cutters",
    
    # Sports & Niche
    "football streaming",
    "ufc streaming",
    "live sports",
    "nba streams",
    "uk streaming",
    "us cable alternatives"
]

BUYER_AUDIENCE_KEYWORDS = [
    "buffering",
    "not working",
    "firestick",
    "tivimate",
    "android tv",
    "smart tv",
    "sports",
    "streaming help",
    "provider recommendation",
    "iptv troubleshooting",
]

SELLER_PROMOTION_KEYWORDS = [
    "reseller",
    "panel",
    "trial",
    "wholesale",
    "server",
    "credits",
    "restream",
    "buy iptv",
    "cheap iptv",
    "panel available",
    "server available",
    "dm for price",
    "credits available",
    "wholesale iptv"
]

BUYER_INTENT_KEYWORDS = [
    "any good iptv",
    "buffering",
    "iptv not working",
    "server down",
    "need provider",
    "any recommendations",
    "best iptv",
    "help request",
    "tivimate setup",
    "firestick help"
]

COMPETITOR_PAIN_SIGNALS = [
    "iptv not working",
    "server down",
    "buffering",
    "need new provider",
    "any good iptv",
    "looking for reliable",
    "channels lagging"
]

INVITE_LINK_PATTERNS = [
    r"t\.me/[a-zA-Z0-9_+]{5,}",
    r"telegram\.me/[a-zA-Z0-9_+]{5,}",
    r"joinchat/[a-zA-Z0-9_-]{10,}"
]

PRIVATE_INVITE_HASH_PATTERN = r"(?:joinchat/|\+)?([\w-]+)$"

DISCOVERY_LIMITS = {
    "max_groups_per_day": 2,
    "max_groups_per_run": 3,
    "join_delay_min": 5,  # minutes
    "join_delay_max": 30, # minutes
    "recent_failure_cooldown_hours": 24,
}

SCORING_THRESHOLDS = {
    "ignore": 40,
    "medium": 70,
    "high": 100 
}

GROUP_QUALITY_THRESHOLDS = {
    "min_members": 80,
    "min_messages_last_24h": 20,
    "min_unique_users_last_24h": 8,
    "min_recent_messages_6h": 4,
    "freshness_window_hours": 18,
    "max_seller_density": 0.12,
    "max_duplicate_promo_ratio": 0.05,
    "min_buyer_signal_ratio": 0.05,
    "min_conversation_ratio": 0.04,
    "approval_score": 68,
    "watchlist_score": 45,
}
