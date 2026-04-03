from __future__ import annotations

import re

from app.services.group_discovery.discovery_config import PRIVATE_INVITE_HASH_PATTERN


def extract_invite_hash(invite_link: str | None) -> str | None:
    if not invite_link:
        return None

    cleaned = invite_link.strip().rstrip("/")
    match = re.search(PRIVATE_INVITE_HASH_PATTERN, cleaned)
    if not match:
        return None
    return match.group(1)
