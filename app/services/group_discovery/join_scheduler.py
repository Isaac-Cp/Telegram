import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select
from telethon import errors, functions

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.group import Group
from app.models.group_join_history import GroupJoinHistory
from app.services.group_discovery.discovery_config import DISCOVERY_LIMITS, GROUP_QUALITY_THRESHOLDS
from app.services.group_discovery.invite_utils import extract_invite_hash
from app.services.human_engine import human_engine
from app.services.telegram_client import telegram_client_manager

logger = logging.getLogger(__name__)


def rank_join_candidates(groups: list[Group]) -> list[Group]:
    now = datetime.now(UTC).replace(tzinfo=None)

    def priority(group: Group) -> tuple[float, int, int, int]:
        freshness_bonus = 0.0
        if group.last_message_timestamp:
            freshness_hours = max(
                0.0,
                (now - group.last_message_timestamp.replace(tzinfo=None)).total_seconds() / 3600,
            )
            freshness_bonus = max(0.0, 12 - freshness_hours)

        composite_score = (
            (group.quality_score or 0) * 0.55
            + (group.authority_score or 0) * 0.30
            + min(group.messages_last_24h or 0, 120) * 0.10
            + min(group.unique_users_last_24h or 0, 40) * 0.25
            + freshness_bonus
            - ((group.seller_density or 0.0) * 100)
        )
        return (
            round(composite_score, 3),
            group.quality_score or 0,
            group.authority_score or 0,
            group.messages_last_24h or 0,
        )

    return sorted(groups, key=priority, reverse=True)


async def _join_group(client, group: Group) -> None:
    if group.username:
        await client(functions.channels.JoinChannelRequest(channel=group.username))
        return

    invite_hash = extract_invite_hash(group.invite_link)
    if invite_hash:
        await client(functions.messages.ImportChatInviteRequest(hash=invite_hash))
        return

    raise ValueError(f"Group {group.id} has no valid username or invite hash")


async def schedule_group_join():
    """
    Safely join the best recently-scored candidate groups.
    """
    if not human_engine.is_within_natural_active_hours():
        return

    settings = get_settings()

    with SessionLocal() as db:
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        recent_joins = db.execute(
            select(func.count(GroupJoinHistory.id)).where(
                and_(
                    GroupJoinHistory.join_time >= one_hour_ago,
                    GroupJoinHistory.status == "success",
                )
            )
        ).scalar() or 0

        if recent_joins >= settings.max_groups_join_per_hour:
            logger.info(
                "[SLIE Joiner] Safe join limit reached (%s/%s per hour). Waiting...",
                recent_joins,
                settings.max_groups_join_per_hour,
            )
            return

        cooldown_cutoff = now - timedelta(hours=DISCOVERY_LIMITS["recent_failure_cooldown_hours"])
        recently_failed_group_ids = set(
            db.execute(
                select(GroupJoinHistory.group_id).where(
                    and_(
                        GroupJoinHistory.join_time >= cooldown_cutoff,
                        GroupJoinHistory.status.in_(["failed", "requested"]),
                    )
                )
            ).scalars().all()
        )

        freshness_cutoff = now - timedelta(hours=GROUP_QUALITY_THRESHOLDS["freshness_window_hours"])
        candidate_groups = db.execute(
            select(Group).where(
                and_(
                    Group.joined.is_(False),
                    Group.eligible_for_join.is_(True),
                    Group.status == "APPROVED",
                    Group.last_scanned.is_not(None),
                    Group.last_message_timestamp.is_not(None),
                    Group.last_message_timestamp >= freshness_cutoff,
                )
            )
        ).scalars().all()

        target_groups = rank_join_candidates(
            [group for group in candidate_groups if group.id not in recently_failed_group_ids]
        )[: DISCOVERY_LIMITS["max_groups_per_run"]]

        if not target_groups:
            return

        for group in target_groups:
            if not await human_engine.authorize_action("group_join"):
                continue

            account = await telegram_client_manager.rotate_account("group_join")
            if not account:
                logger.info("[SLIE Joiner] All accounts reached daily limit. Join scheduler: PAUSED.")
                break

            try:
                await human_engine.apply_randomized_delay("group_join")
                client = await telegram_client_manager.get_client(phone_number=account.phone_number)

                logger.info("[SLIE Joiner] Account %s joining group: %s", account.phone_number, group.name)
                await _join_group(client, group)

                group.joined = True
                group.status = "joined"
                db.add(
                    GroupJoinHistory(
                        group_id=group.id,
                        account_id=account.id,
                        join_time=datetime.utcnow(),
                        status="success",
                    )
                )
                await telegram_client_manager.track_account_limits(account.phone_number, "group_join")
                db.commit()
                logger.info("[SLIE Joiner] joined group: %s", group.name)

            except errors.UserAlreadyParticipantError:
                group.joined = True
                group.status = "joined"
                db.add(
                    GroupJoinHistory(
                        group_id=group.id,
                        account_id=account.id,
                        join_time=datetime.utcnow(),
                        status="success",
                    )
                )
                db.commit()
                logger.info("[SLIE Joiner] Account already in group: %s", group.name)
            except errors.InviteRequestSentError:
                group.status = "PENDING_APPROVAL"
                group.eligible_for_join = False
                db.add(
                    GroupJoinHistory(
                        group_id=group.id,
                        account_id=account.id,
                        join_time=datetime.utcnow(),
                        status="requested",
                    )
                )
                db.commit()
                logger.info("[SLIE Joiner] Join request submitted for group: %s", group.name)
            except errors.ChannelsTooMuchError:
                db.add(
                    GroupJoinHistory(
                        group_id=group.id,
                        account_id=account.id,
                        join_time=datetime.utcnow(),
                        status="failed",
                    )
                )
                db.commit()
                logger.warning("[SLIE Joiner] Telegram account hit join capacity. Halting join cycle.")
                break
            except (errors.InviteHashExpiredError, errors.InviteHashInvalidError, errors.ChannelPrivateError, ValueError) as exc:
                logger.error("[SLIE Joiner] Failed to join %s: %s", group.name, exc)
                group.status = "REJECTED"
                group.eligible_for_join = False
                db.add(
                    GroupJoinHistory(
                        group_id=group.id,
                        account_id=account.id,
                        join_time=datetime.utcnow(),
                        status="failed",
                    )
                )
                db.commit()
            except Exception as exc:
                logger.error("[SLIE Joiner] Failed to join %s: %s", group.name, exc)
                group.status = "failed"
                group.eligible_for_join = False
                db.add(
                    GroupJoinHistory(
                        group_id=group.id,
                        account_id=account.id,
                        join_time=datetime.utcnow(),
                        status="failed",
                    )
                )
                db.commit()
