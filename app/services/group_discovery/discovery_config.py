TARGET_KEYWORDS = [
    "iptv",
    "iptv help",
    "iptv discussion",
    "streaming help",
    "smart tv channels"
]

SELLER_PROMOTION_KEYWORDS = [
    "buy iptv",
    "cheap iptv",
    "iptv reseller",
    "panel available",
    "server available",
    "dm for price",
    "credits available",
    "wholesale iptv"
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

DISCOVERY_LIMITS = {
    "max_groups_per_day": 2,
    "join_delay_min": 5,  # minutes
    "join_delay_max": 30, # minutes
}

SCORING_THRESHOLDS = {
    "ignore": 40,
    "medium": 70,
    "high": 100 
}
