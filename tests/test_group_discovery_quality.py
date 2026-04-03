from datetime import UTC, datetime, timedelta

from app.models.group import Group
from app.services.group_discovery.group_quality import (
    SampledMessage,
    analyze_sampled_messages,
    score_group_candidate,
)
from app.services.group_discovery.invite_utils import extract_invite_hash
from app.services.group_discovery.join_scheduler import rank_join_candidates
from app.services.seller_detector import seller_detector


def _message(text: str, sender: str, hours_ago: int, *, is_reply: bool = False) -> SampledMessage:
    return SampledMessage(
        text=text,
        sender_id=sender,
        sent_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours_ago),
        is_reply=is_reply,
    )


def test_seller_detector_flags_seller_hub():
    snapshot = seller_detector.analyze_message_batch(
        [
            "DM for price reseller panel available",
            "DM for price reseller panel available",
            "Best server trial available today",
            "Wholesale credits available",
            "Anyone know why tivimate is buffering?",
        ]
    )

    assert snapshot.market_type == "SELLER HUB"
    assert snapshot.seller_ratio > 0.12
    assert snapshot.duplicate_promo_ratio > 0


def test_group_quality_approves_active_buyer_community():
    messages = [
        _message("Any good IPTV for football on firestick?", "1", 1),
        _message("My provider is buffering badly on tivimate", "2", 1, is_reply=True),
        _message("Need a reliable provider recommendation", "3", 2),
        _message("Does anyone have setup help for android tv?", "4", 2, is_reply=True),
        _message("IPTV not working tonight, any fix?", "5", 3),
        _message("Looking for a better provider, current one keeps lagging", "6", 4),
        _message("Firestick help please, channels keep freezing", "7", 5),
        _message("Any recommendations for sports streaming?", "8", 5),
    ]
    messages.extend(
        _message(f"General streaming chat {index}", str(index + 10), 4)
        for index in range(18)
    )

    metrics = analyze_sampled_messages(messages, now=datetime.now(UTC).replace(tzinfo=None))
    decision = score_group_candidate(
        name="Firestick IPTV Help",
        description="buffering fixes, tivimate help, provider recommendation chat",
        members_count=1500,
        metrics=metrics,
        ai_intent_scores={"BUYER_INTENT": 0.24, "SELLER_PROMOTION": 0.02, "GENERAL_CHAT": 0.74},
        is_megagroup=True,
        is_broadcast=False,
        is_scam=False,
        is_fake=False,
        is_restricted=False,
        request_needed=False,
        join_request_enabled=False,
        slowmode_seconds=30,
        now=datetime.now(UTC).replace(tzinfo=None),
    )

    assert decision.status == "APPROVED"
    assert decision.eligible is True
    assert decision.market_type in {"BUYER COMMUNITY", "DISCUSSION GROUP"}
    assert decision.score >= 68


def test_group_quality_rejects_stale_low_signal_group():
    messages = [
        _message("hello everyone", "1", 30),
        _message("nice stream", "2", 28),
        _message("ok", "3", 27),
    ]

    metrics = analyze_sampled_messages(messages, now=datetime.now(UTC).replace(tzinfo=None))
    decision = score_group_candidate(
        name="Quiet Chat",
        description="general talk",
        members_count=120,
        metrics=metrics,
        ai_intent_scores={"BUYER_INTENT": 0.01, "SELLER_PROMOTION": 0.0, "GENERAL_CHAT": 0.99},
        is_megagroup=True,
        is_broadcast=False,
        is_scam=False,
        is_fake=False,
        is_restricted=False,
        request_needed=False,
        join_request_enabled=False,
        slowmode_seconds=None,
        now=datetime.now(UTC).replace(tzinfo=None),
    )

    assert decision.status == "REJECTED"
    assert decision.eligible is False
    assert any("stale" in reason or "activity" in reason for reason in decision.reasons)


def test_extract_invite_hash_handles_private_links():
    assert extract_invite_hash("https://t.me/+AbCdEf123") == "AbCdEf123"
    assert extract_invite_hash("https://t.me/joinchat/Qwerty987") == "Qwerty987"


def test_rank_join_candidates_prefers_fresher_higher_quality_groups():
    older_group = Group(name="Older")
    older_group.quality_score = 82
    older_group.authority_score = 80
    older_group.messages_last_24h = 55
    older_group.unique_users_last_24h = 20
    older_group.seller_density = 0.03
    older_group.last_message_timestamp = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=10)

    fresh_group = Group(name="Fresh")
    fresh_group.quality_score = 80
    fresh_group.authority_score = 79
    fresh_group.messages_last_24h = 60
    fresh_group.unique_users_last_24h = 22
    fresh_group.seller_density = 0.02
    fresh_group.last_message_timestamp = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)

    ranked = rank_join_candidates([older_group, fresh_group])

    assert ranked[0].name == "Fresh"
