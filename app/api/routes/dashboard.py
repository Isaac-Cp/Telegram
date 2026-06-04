import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import get_settings
from app.core import security
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import (
    get_conversations_elite,
    get_conversions_elite,
    get_dashboard_summary,
    get_groups_elite,
    get_leads_elite,
    get_reseller_prospects_elite,
    get_stats,
    get_high_intent_buyers_elite,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "dashboard_settings.json"
TOKEN_TTL_SECONDS = 60 * 60 * 24
ACTIVE_TOKENS: dict[str, float] = {}


class DashboardLoginRequest(BaseModel):
    password: str = Field(min_length=1)


class DashboardSettingsPayload(BaseModel):
    target_tags: list[str] = Field(default_factory=list)
    search_tags: list[str] = Field(default_factory=list)
    brand_tags: list[str] = Field(default_factory=list)
    watch_terms: list[str] = Field(default_factory=list)
    lead_score_threshold: int = 70
    daily_dm_limit: int = 50
    auto_join_groups: bool = False
    telegram_outreach_enabled: bool = False
    notes: str = ""


def _default_settings() -> dict[str, Any]:
    return {
        "target_tags": ["iptv", "reseller", "trial users", "support issues"],
        "search_tags": ["buffering", "refund", "cheap iptv", "best provider"],
        "brand_tags": ["Streamexpert", "sales agent", "support crm"],
        "watch_terms": ["downtime", "ban", "competitor", "migration"],
        "lead_score_threshold": 70,
        "daily_dm_limit": 50,
        "auto_join_groups": False,
        "telegram_outreach_enabled": False,
        "notes": "Use this panel to keep dashboard targeting terms organized.",
    }


def _normalize_tags(items: list[str]) -> list[str]:
    seen = set()
    normalized: list[str] = []
    for item in items:
        value = item.strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _load_settings() -> dict[str, Any]:
    base = _default_settings()
    if not SETTINGS_PATH.exists():
        return base
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Dashboard settings fallback due to read error: %s", exc)
        return base

    return {
        "target_tags": _normalize_tags(data.get("target_tags", base["target_tags"])),
        "search_tags": _normalize_tags(data.get("search_tags", base["search_tags"])),
        "brand_tags": _normalize_tags(data.get("brand_tags", base["brand_tags"])),
        "watch_terms": _normalize_tags(data.get("watch_terms", base["watch_terms"])),
        "lead_score_threshold": int(data.get("lead_score_threshold", base["lead_score_threshold"]) or 0),
        "daily_dm_limit": int(data.get("daily_dm_limit", base["daily_dm_limit"]) or 0),
        "auto_join_groups": bool(data.get("auto_join_groups", base["auto_join_groups"])),
        "telegram_outreach_enabled": bool(data.get("telegram_outreach_enabled", base["telegram_outreach_enabled"])),
        "notes": str(data.get("notes", base["notes"])).strip(),
    }


def _save_settings(payload: DashboardSettingsPayload) -> dict[str, Any]:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "target_tags": _normalize_tags(payload.target_tags),
        "search_tags": _normalize_tags(payload.search_tags),
        "brand_tags": _normalize_tags(payload.brand_tags),
        "watch_terms": _normalize_tags(payload.watch_terms),
        "lead_score_threshold": max(0, min(100, int(payload.lead_score_threshold))),
        "daily_dm_limit": max(0, int(payload.daily_dm_limit)),
        "auto_join_groups": bool(payload.auto_join_groups),
        "telegram_outreach_enabled": bool(payload.telegram_outreach_enabled),
        "notes": payload.notes.strip(),
    }
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _apply_dashboard_tokens(html: str, active_page: str) -> str:
    return html.replace("__ACTIVE_PAGE__", active_page)


def _admin_password() -> str:
    # Prefer configured settings over raw environment access for consistency
    try:
        return get_settings().dashboard_admin_password
    except Exception:
        return os.getenv("DASHBOARD_ADMIN_PASSWORD", "changeme")


def _require_dashboard_auth(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token.")
    token = authorization.split(" ", 1)[1].strip()
    payload = security.decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired authorization token.")
    return payload


def _fallback_stats() -> dict[str, Any]:
    return {
        "total_groups_joined": 0,
        "messages_analyzed": 0,
        "leads_detected": 0,
        "conversions": 0,
        "conversion_rate": 0.0,
        "high_prob_leads": 0,
        "influence_distribution": {"leader": 0, "power_user": 0, "regular": 0},
        "competitor_stats": [],
        "ltv_distribution": {},
        "account_health": [],
        "activity_log": [],
        "dms_sent": 0,
    }


def _fallback_summary() -> dict[str, Any]:
    return {
        "contacts_total": 0,
        "active_consents": 0,
        "open_conversations": 0,
        "open_tickets": 0,
        "follow_ups_due": 0,
        "inbound_messages_today": 0,
        "outbound_messages_today": 0,
        "groups_joined": 0,
        "messages_analyzed": 0,
        "leads_detected_total": 0,
        "conversions": 0,
        "leads_detected_today": 0,
        "public_replies_sent": 0,
        "dms_sent": 0,
        "reply_rate": 0.0,
        "conversion_rate": 0.0,
        "high_value_leads": 0,
        "reseller_prospects": 0,
        "average_ltv_score": 0.0,
        "ltv_distribution": {},
        "problem_distribution": {},
        "persona_performance": [],
        "account_health": [],
        "recent_leads": [],
        "top_groups": [],
        "daily_trend": [],
        "conversion_funnel": [],
    }


def _safe_call(label: str, fn, fallback, *args):
    try:
        return fn(*args)
    except Exception as exc:
        logger.warning("Dashboard fallback for %s: %s", label, exc)
        return fallback


def _build_dashboard_html(active_page: str) -> str:
    template_path = Path(__file__).resolve().parents[2] / "templates" / "slie_dashboard.html"
    # Fallback to app/templates if not in root templates
    if not template_path.exists():
        template_path = Path(__file__).resolve().parents[1] / "templates" / "slie_dashboard.html"
        
    if template_path.exists():
        return _apply_dashboard_tokens(template_path.read_text(encoding="utf-8"), active_page)

    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SLIE Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="/dashboard/js/theme-config.js"></script>
    <link rel="stylesheet" href="/dashboard/css/theme-core.css">
</head>
<body class="premium-gradient flex items-center justify-center min-h-screen p-6">
    <div class="glass-panel p-12 text-center max-w-md shadow-2xl relative z-10">
        <div class="w-16 h-16 bg-gradient-to-br from-highlight to-deep-blue rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-clay-button animate-float">
            <svg class="w-8 h-8 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
        </div>
        <h1 class="text-3xl font-extrabold text-white mb-2 tracking-tight">Revenue Command</h1>
        <p class="text-slate-400 text-sm mb-8 font-medium">Premium Intelligence Interface</p>
        
        <div class="clay-card p-6 space-y-4">
            <div class="animate-pulse flex space-x-4 justify-center">
                <div class="h-2 w-2 bg-accent rounded-full shadow-[0_0_12px_rgba(100,255,218,0.6)]"></div>
                <div class="h-2 w-2 bg-accent rounded-full shadow-[0_0_12px_rgba(100,255,218,0.6)]"></div>
                <div class="h-2 w-2 bg-accent rounded-full shadow-[0_0_12px_rgba(100,255,218,0.6)]"></div>
            </div>
            <p class="text-[10px] text-slate-500 uppercase tracking-widest font-bold">Template loading or unavailable</p>
        </div>
    </div>
</body>
</html>
""".replace("__ACTIVE_PAGE__", active_page)


def _render_page(active_page: str) -> HTMLResponse:
    return HTMLResponse(_build_dashboard_html(active_page))


@router.post("/auth/login")
def dashboard_login(payload: DashboardLoginRequest):
    settings = get_settings()
    # Check against plain password or hashed password if available
    is_valid = False
    if settings.dashboard_password_hash:
        is_valid = security.verify_password(payload.password, settings.dashboard_password_hash)
    else:
        is_valid = payload.password == _admin_password()
        
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid password.")
        
    access_token = security.create_access_token(subject="admin")
    return {"token": access_token, "expires_in": settings.access_token_expire_minutes * 60}


@router.get("/settings-config")
def dashboard_settings_config(authorization: str | None = Header(default=None)):
    if authorization:
        _require_dashboard_auth(authorization)
    return _load_settings()


@router.put("/settings-config")
def update_dashboard_settings(
    payload: DashboardSettingsPayload,
    authorization: str | None = Header(default=None),
):
    _require_dashboard_auth(authorization)
    return _save_settings(payload)


@router.get("/stats")
def stats_endpoint(db: Session = Depends(get_db)):
    return _safe_call("stats", get_stats, _fallback_stats(), db)


@router.get("/leads")
def leads_endpoint(db: Session = Depends(get_db)):
    return _safe_call("leads", get_leads_elite, [], db)


@router.get("/groups")
def groups_endpoint(db: Session = Depends(get_db)):
    return _safe_call("groups", get_groups_elite, [], db)


@router.get("/conversions")
def conversions_endpoint(db: Session = Depends(get_db)):
    return _safe_call("conversions", get_conversions_elite, [], db)


@router.get("/reseller-prospects")
def reseller_prospects_endpoint(db: Session = Depends(get_db)):
    return _safe_call("reseller-prospects", get_reseller_prospects_elite, [], db)


@router.get("/high-intent-buyers")
def high_intent_buyers_endpoint(db: Session = Depends(get_db)):
    """Show the 20 highest-intent buyers detected in the last 7 days."""
    return _safe_call("high-intent-buyers", get_high_intent_buyers_elite, [], db)


@router.get("/conversations")
def conversations_endpoint(username: str | None = None, db: Session = Depends(get_db)):
    return _safe_call("conversations", get_conversations_elite, [], db, username)


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary_endpoint(db: Session = Depends(get_db)) -> DashboardSummary:
    return _safe_call("summary", get_dashboard_summary, _fallback_summary(), db)


@router.get("/", response_class=HTMLResponse)
def dashboard_root():
    return _render_page("overview")


@router.get("/overview", response_class=HTMLResponse)
def dashboard_overview():
    return _render_page("overview")


@router.get("/activity", response_class=HTMLResponse)
def dashboard_activity():
    return _render_page("activity")


@router.get("/pipeline", response_class=HTMLResponse)
def dashboard_pipeline():
    return _render_page("pipeline")


@router.get("/watch", response_class=HTMLResponse)
def dashboard_watch():
    return _render_page("watch")


@router.get("/targeting", response_class=HTMLResponse)
def dashboard_targeting():
    return _render_page("targeting")


@router.get("/settings", response_class=HTMLResponse)
def dashboard_settings_page():
    return _render_page("settings")


@router.get("/styleguide", response_class=HTMLResponse)
def dashboard_styleguide_page():
    return _render_page("styleguide")
