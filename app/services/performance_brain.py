from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import case, desc, func, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.models.enums import ConversionStage
from app.models.group import Group
from app.models.lead import Lead
from app.models.telegram_account import TelegramAccount

logger = logging.getLogger(__name__)


class PerformanceBrain:
    """Turns recent bot performance into bounded operational decisions."""

    def analyze(
        self,
        db: Session,
        dashboard_settings: dict[str, Any] | None = None,
        window_days: int = 7,
    ) -> dict[str, Any]:
        settings = get_settings()
        dashboard_settings = dashboard_settings or {}
        threshold = int(dashboard_settings.get("lead_score_threshold", 70) or 70)
        dm_limit = int(dashboard_settings.get("daily_dm_limit", settings.max_dms_per_day) or settings.max_dms_per_day)
        cutoff = utcnow() - timedelta(days=window_days)

        total_leads = self._count_model(db, Lead, Lead.created_at >= cutoff)
        contacted = self._count_model(
            db,
            Lead,
            Lead.created_at >= cutoff,
            or_(
                Lead.dm_sent.is_(True),
                Lead.public_reply_sent.is_(True),
                Lead.conversion_stage != ConversionStage.NEW,
            ),
        )
        dms_sent = self._count_model(db, Lead, Lead.last_contact >= cutoff, Lead.dm_sent.is_(True))
        public_replies = self._count_model(db, Lead, Lead.last_contact >= cutoff, Lead.public_reply_sent.is_(True))
        responses = self._count_model(
            db,
            Lead,
            Lead.last_contact >= cutoff,
            Lead.conversion_stage.in_(
                [ConversionStage.RESPONDED, ConversionStage.INTERESTED, ConversionStage.CONVERTED]
            ),
        )
        conversions = self._count_model(
            db,
            Lead,
            Lead.last_contact >= cutoff,
            Lead.conversion_stage == ConversionStage.CONVERTED,
        )
        high_score_leads = self._count_model(db, Lead, Lead.created_at >= cutoff, Lead.lead_score >= threshold)
        avg_score = db.query(func.avg(Lead.lead_score)).filter(Lead.created_at >= cutoff).scalar() or 0.0
        active_accounts = self._count_model(db, TelegramAccount, TelegramAccount.status == "active")
        limited_accounts = self._count_model(db, TelegramAccount, TelegramAccount.status.in_(["limited", "banned"]))
        joined_groups = self._count_model(db, Group, Group.joined.is_(True))
        approved_waiting = self._count_model(db, Group, Group.status == "approved", Group.joined.is_(False))

        response_rate = self._rate(responses, max(dms_sent, public_replies))
        conversion_rate = self._rate(conversions, total_leads)
        contact_rate = self._rate(contacted, total_leads)

        metrics = {
            "window_days": window_days,
            "leads": total_leads,
            "contacted": contacted,
            "contact_rate": contact_rate,
            "dms_sent": dms_sent,
            "public_replies": public_replies,
            "responses": responses,
            "response_rate": response_rate,
            "conversions": conversions,
            "conversion_rate": conversion_rate,
            "high_score_leads": high_score_leads,
            "average_lead_score": round(float(avg_score), 2),
            "active_accounts": active_accounts,
            "limited_accounts": limited_accounts,
            "joined_groups": joined_groups,
            "approved_groups_waiting": approved_waiting,
        }

        decisions = self._build_decisions(settings, dashboard_settings, metrics, threshold, dm_limit)
        top_groups = self._top_groups(db, cutoff)
        top_personas = self._top_personas(db, cutoff)
        if top_groups:
            decisions.append(
                self._decision(
                    key="focus_best_group",
                    title="Focus the best-performing group",
                    priority="medium",
                    confidence=0.76,
                    action=f"Prioritize scanning and reply review for {top_groups[0]['name']}.",
                    reason="This group is producing the strongest lead or conversion signal in the current window.",
                    evidence={"group": top_groups[0]},
                )
            )
        if top_personas:
            decisions.append(
                self._decision(
                    key="favor_best_persona",
                    title="Favor the top persona",
                    priority="low",
                    confidence=0.68,
                    action=f"Use {top_personas[0]['name']} more often for similar leads until the next review.",
                    reason="The persona has the best observed conversion rate among personas with recent leads.",
                    evidence={"persona": top_personas[0]},
                )
            )

        if not decisions:
            decisions.append(
                self._decision(
                    key="steady_state",
                    title="Keep current strategy",
                    priority="low",
                    confidence=0.62,
                    action="Keep collecting data and review again after the next scheduler cycle.",
                    reason="No urgent performance bottleneck was detected from the current data.",
                    evidence=metrics,
                )
            )

        proposed_settings = self._merge_setting_changes(decisions)
        mode = self._mode(decisions)
        return {
            "mode": mode,
            "summary": self._summary(mode, metrics),
            "metrics": metrics,
            "decisions": decisions,
            "proposed_settings": proposed_settings,
            "top_groups": top_groups,
            "top_personas": top_personas,
            "guardrails": [
                "No code self-modification.",
                "No automatic increase above configured daily DM safety limits.",
                "No outbound automation when TELEGRAM_ENABLED=false or the session is invalid.",
                "Operator review is required before applying proposed setting changes.",
            ],
        }

    def _build_decisions(self, settings, dashboard_settings, metrics, threshold: int, dm_limit: int) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        outreach_enabled = bool(dashboard_settings.get("telegram_outreach_enabled", False))

        if not settings.telegram_enabled:
            decisions.append(
                self._decision(
                    key="telegram_disabled",
                    title="Telegram automation is disabled",
                    priority="high",
                    confidence=0.98,
                    action="Enable TELEGRAM_ENABLED only on the always-on bot host after the session is fixed.",
                    reason="The bot cannot scan, reply, or DM while Telegram automation is disabled.",
                    evidence={"telegram_enabled": False},
                )
            )
            return decisions

        if not settings.telegram_session_string:
            decisions.append(
                self._decision(
                    key="missing_session",
                    title="Telegram session is missing",
                    priority="critical",
                    confidence=0.99,
                    action="Generate a fresh SESSION_STRING and deploy it to the single host that owns the bot.",
                    reason="Without a session string, Telethon cannot connect to Telegram.",
                    evidence={"session_configured": False},
                )
            )

        if metrics["limited_accounts"] > 0 or metrics["active_accounts"] == 0:
            decisions.append(
                self._decision(
                    key="account_health",
                    title="Review Telegram account health",
                    priority="high",
                    confidence=0.82,
                    action="Check account status, proxy health, and whether the same session is running in multiple places.",
                    reason="Limited, banned, or missing active accounts prevent reliable automation.",
                    evidence={
                        "active_accounts": metrics["active_accounts"],
                        "limited_accounts": metrics["limited_accounts"],
                    },
                )
            )

        if metrics["leads"] < 5:
            decisions.append(
                self._decision(
                    key="collect_more_signal",
                    title="Collect more lead signal",
                    priority="medium",
                    confidence=0.7,
                    action="Run discovery and broaden search/watch terms before judging conversion performance.",
                    reason="There are not enough recent leads to make a strong performance decision.",
                    evidence={"recent_leads": metrics["leads"]},
                )
            )
            return decisions

        if metrics["contact_rate"] < 20:
            decisions.append(
                self._decision(
                    key="outreach_bottleneck",
                    title="Outreach is not reaching enough leads",
                    priority="high",
                    confidence=0.78,
                    action="Verify Telegram connectivity, outreach settings, active hours, and response jobs.",
                    reason="Recent leads exist, but very few are being contacted or moved beyond NEW.",
                    evidence={"contact_rate": metrics["contact_rate"], "leads": metrics["leads"]},
                )
            )

        if outreach_enabled and metrics["dms_sent"] > 0 and metrics["response_rate"] < 10:
            decisions.append(
                self._decision(
                    key="raise_quality_bar",
                    title="Raise lead quality bar",
                    priority="high",
                    confidence=0.74,
                    action="Contact fewer low-quality leads and require stronger intent before DM.",
                    reason="DMs are being sent, but response rate is weak.",
                    evidence={"response_rate": metrics["response_rate"], "dms_sent": metrics["dms_sent"]},
                    setting_changes={
                        "lead_score_threshold": min(95, threshold + 5),
                        "daily_dm_limit": max(1, min(dm_limit, settings.max_dms_per_day) - 1),
                    },
                )
            )

        if metrics["response_rate"] >= 30 and metrics["conversion_rate"] >= 8 and metrics["high_score_leads"] > metrics["dms_sent"]:
            decisions.append(
                self._decision(
                    key="expand_carefully",
                    title="Expand cautiously",
                    priority="medium",
                    confidence=0.66,
                    action="Use one more daily DM only if account health is clean and active hours are respected.",
                    reason="Recent replies and conversions are strong, and high-score leads remain uncontacted.",
                    evidence={
                        "response_rate": metrics["response_rate"],
                        "conversion_rate": metrics["conversion_rate"],
                        "high_score_leads": metrics["high_score_leads"],
                    },
                    setting_changes={
                        "daily_dm_limit": min(settings.max_dms_per_day, dm_limit + 1),
                    },
                )
            )

        if metrics["approved_groups_waiting"] > 0 and metrics["joined_groups"] == 0:
            decisions.append(
                self._decision(
                    key="join_queue_waiting",
                    title="Approved groups are waiting",
                    priority="medium",
                    confidence=0.72,
                    action="Run the join scheduler after confirming account health and daily join limits.",
                    reason="Groups are approved but not joined, so the scanner has fewer live sources.",
                    evidence={"approved_groups_waiting": metrics["approved_groups_waiting"]},
                )
            )

        return decisions

    def _top_groups(self, db: Session, cutoff) -> list[dict[str, Any]]:
        rows = (
            db.query(
                Group.name,
                func.count(Lead.id).label("leads"),
                func.avg(Lead.lead_score).label("avg_score"),
                func.sum(case((Lead.conversion_stage == ConversionStage.CONVERTED, 1), else_=0)).label("conversions"),
            )
            .join(Lead, Lead.group_id == Group.id)
            .filter(Lead.created_at >= cutoff)
            .group_by(Group.id, Group.name)
            .order_by(desc("conversions"), desc("avg_score"), desc("leads"))
            .limit(5)
            .all()
        )
        return [
            {
                "name": row.name,
                "leads": int(row.leads or 0),
                "average_score": round(float(row.avg_score or 0), 2),
                "conversions": int(row.conversions or 0),
            }
            for row in rows
        ]

    def _top_personas(self, db: Session, cutoff) -> list[dict[str, Any]]:
        rows = (
            db.query(
                Lead.persona_id,
                func.count(Lead.id).label("leads"),
                func.sum(case((Lead.conversion_stage == ConversionStage.CONVERTED, 1), else_=0)).label("conversions"),
            )
            .filter(Lead.created_at >= cutoff, Lead.persona_id.is_not(None))
            .group_by(Lead.persona_id)
            .order_by(desc("conversions"), desc("leads"))
            .limit(5)
            .all()
        )
        personas = []
        for row in rows:
            leads = int(row.leads or 0)
            conversions = int(row.conversions or 0)
            personas.append(
                {
                    "name": row.persona_id,
                    "leads": leads,
                    "conversions": conversions,
                    "conversion_rate": self._rate(conversions, leads),
                }
            )
        return personas

    @staticmethod
    def _count_model(db: Session, model, *filters) -> int:
        query = db.query(func.count(model.id))
        for item in filters:
            query = query.filter(item)
        return int(query.scalar() or 0)

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round((numerator / denominator * 100), 2) if denominator else 0.0

    @staticmethod
    def _decision(
        *,
        key: str,
        title: str,
        priority: str,
        confidence: float,
        action: str,
        reason: str,
        evidence: dict[str, Any],
        setting_changes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "priority": priority,
            "confidence": confidence,
            "action": action,
            "reason": reason,
            "evidence": evidence,
            "setting_changes": setting_changes or {},
        }

    @staticmethod
    def _merge_setting_changes(decisions: list[dict[str, Any]]) -> dict[str, Any]:
        proposed: dict[str, Any] = {}
        for item in decisions:
            proposed.update(item.get("setting_changes") or {})
        return proposed

    @staticmethod
    def _mode(decisions: list[dict[str, Any]]) -> str:
        priorities = {item["priority"] for item in decisions}
        if "critical" in priorities:
            return "protect"
        if "high" in priorities:
            return "diagnose"
        if "medium" in priorities:
            return "optimize"
        return "observe"

    @staticmethod
    def _summary(mode: str, metrics: dict[str, Any]) -> str:
        if mode == "protect":
            return "Protection mode: fix connectivity or account health before outreach."
        if mode == "diagnose":
            return "Diagnosis mode: recent data shows a bottleneck that needs operator review."
        if mode == "optimize":
            return "Optimization mode: enough signal exists for cautious tuning."
        return f"Observation mode: tracking {metrics['leads']} recent leads and waiting for stronger signal."


performance_brain = PerformanceBrain()
