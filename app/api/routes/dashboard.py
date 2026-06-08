import json
import logging
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import get_settings
from app.core import security
from app.models.dashboard_setting import DashboardSetting
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

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
logger = logging.getLogger(__name__)
security_scheme = HTTPBearer()

SETTINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "dashboard_settings.json"
TOKEN_TTL_SECONDS = 60 * 60 * 24
ACTIVE_TOKENS: dict[str, float] = {}
DASHBOARD_AUTH_COOKIE = "slie_dashboard_access"
DASHBOARD_CONTROL_COOKIE = "slie_control_access"


class DashboardLoginRequest(BaseModel):
    password: str = Field(min_length=1)
    scope: str = Field(default="dashboard")


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


def _sanitize_settings(data: dict[str, Any]) -> dict[str, Any]:
    base = _default_settings()
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


def _load_legacy_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return _default_settings()
    try:
        return _sanitize_settings(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except Exception as exc:
        logger.warning("Dashboard settings legacy import skipped due to read error: %s", exc)
        return _default_settings()


def _load_settings(db: Session) -> dict[str, Any]:
    row = db.query(DashboardSetting).filter(DashboardSetting.key == "main").one_or_none()
    if row:
        return _sanitize_settings(row.value or {})

    data = _load_legacy_settings()
    row = DashboardSetting(key="main", value=data)
    db.add(row)
    db.commit()
    return data


def _save_settings(db: Session, payload: DashboardSettingsPayload) -> dict[str, Any]:
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
    row = db.query(DashboardSetting).filter(DashboardSetting.key == "main").one_or_none()
    if row:
        row.value = data
    else:
        db.add(DashboardSetting(key="main", value=data))
    db.commit()
    return data


def _apply_dashboard_tokens(html: str, active_page: str) -> str:
    return html.replace("__ACTIVE_PAGE__", active_page)


def _admin_password() -> str:
    # Prefer configured settings over raw environment access for consistency
    try:
        return get_settings().dashboard_admin_password
    except Exception:
        return os.getenv("DASHBOARD_ADMIN_PASSWORD", "changeme")


def _control_password() -> str:
    try:
        return get_settings().dashboard_control_password
    except Exception:
        return os.getenv("DASHBOARD_CONTROL_PASSWORD", "control-changeme")


def _password_matches(plain_password: str, configured_password: str, configured_hash: str = "") -> bool:
    if configured_hash:
        return security.verify_password(plain_password, configured_hash)
    return plain_password == configured_password


def get_current_admin(token: HTTPAuthorizationCredentials = Depends(security_scheme)) -> dict:
    payload = security.decode_token(token.credentials)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
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
        "high_prob_leads": 0,
        "high_value_leads": 0,
        "reseller_prospects": 0,
        "average_ltv_score": 0.0,
        "ltv_distribution": {},
        "problem_distribution": {},
        "influence_distribution": {},
        "sentiment_trends": {},
        "hourly_heatmap": [],
        "persona_performance": [],
        "account_health": [],
        "competitor_stats": [],
        "activity_log": [],
        "recent_events": [],
        "crm_trend": [],
        "ticket_status_breakdown": {},
        "ticket_priority_breakdown": {},
        "consent_scope_breakdown": {},
        "lifecycle_stage_breakdown": {},
        "recent_leads": [],
        "top_groups": [],
        "daily_trend": [],
        "conversion_funnel": [],
    }


async def _async_safe_call(label: str, fn, fallback, *args):
    try:
        return await fn(*args)
    except Exception as exc:
        logger.warning("Dashboard fallback for %s: %s", label, exc)
        return fallback


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
    <title>SLIE Intelligence | Command Access</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@700&family=Manrope:wght@600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-deep: #010409;
            --accent: #58a6ff;
            --clay-bg: #161b22;
            --clay-shadow: 20px 20px 60px rgba(0, 0, 0, 0.8), -10px -10px 40px rgba(255, 255, 255, 0.03);
            --clay-inner: inset 10px 10px 20px rgba(255, 255, 255, 0.05), inset -10px -10px 20px rgba(0, 0, 0, 0.6);
        }
        body { background: var(--bg-deep); font-family: 'Manrope', sans-serif; color: #c9d1d9; }
        .classic { font-family: 'Cormorant Garamond', serif; }
        .clay-card {
            background: var(--clay-bg);
            border-radius: 40px;
            box-shadow: var(--clay-shadow), var(--clay-inner);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-6">
    <div class="clay-card p-12 text-center max-w-md w-full">
        <div class="w-20 h-20 bg-[#161b22] rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-[10px_10px_20px_rgba(0,0,0,0.6),-5px_-5px_15px_rgba(255,255,255,0.02)]">
            <svg class="w-10 h-10 text-[#58a6ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
        </div>
        <h1 class="text-4xl font-bold text-white mb-3 classic">Revenue Command</h1>
        <p class="text-slate-400 text-sm mb-10 font-semibold tracking-widest uppercase">Premium Intelligence Interface</p>
        
        <div class="p-8 space-y-4">
            <div class="flex space-x-4 justify-center">
                <div class="h-3 w-3 bg-[#58a6ff] rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                <div class="h-3 w-3 bg-[#58a6ff] rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                <div class="h-3 w-3 bg-[#58a6ff] rounded-full animate-bounce" style="animation-delay: 0.3s"></div>
            </div>
            <p class="text-xs text-slate-500 uppercase tracking-widest font-bold mt-4">System Initializing...</p>
        </div>
    </div>
</body>
</html>
""".replace("__ACTIVE_PAGE__", active_page)


def _render_page(active_page: str) -> HTMLResponse:
    return HTMLResponse(_build_dashboard_html(active_page))


def _settings_cookie_payload(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(DASHBOARD_CONTROL_COOKIE)
    if not token:
        return None
    return security.decode_token(token)


def _build_settings_auth_gate_html() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <meta name="theme-color" content="#010718">
    <title>SLIE Control Access</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/dashboard/styles.css">
</head>
<body>
    <div class="liquid-bg"></div>
    <main class="control-auth-shell">
        <section class="clay-card control-auth-card" aria-labelledby="control-auth-title">
            <div class="control-auth-mark">S</div>
            <span class="section-kicker">Secure Control</span>
            <h1 id="control-auth-title" class="classic-text">Control page locked</h1>
            <p>Enter the Control access key to manage live targeting, outreach, and runtime settings.</p>
            <form id="controlAuthForm" class="control-auth-form">
                <input id="controlPassword" type="password" autocomplete="current-password" placeholder="Access key" required>
                <button class="clay-btn" type="submit">Unlock Control</button>
                <small id="controlAuthError" role="alert"></small>
            </form>
        </section>
    </main>
    <script>
        document.getElementById('controlAuthForm').addEventListener('submit', async (event) => {
            event.preventDefault();
            const error = document.getElementById('controlAuthError');
            error.textContent = '';
            const password = document.getElementById('controlPassword').value;
            try {
                const response = await fetch('/api/v1/dashboard/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password, scope: 'control' })
                });
                if (!response.ok) {
                    error.textContent = 'Invalid access key.';
                    return;
                }
                const data = await response.json();
                localStorage.setItem('slie_token', data.token);
                window.location.replace('/api/v1/dashboard/settings');
            } catch (errorValue) {
                error.textContent = 'Unable to unlock Control right now.';
            }
        });
    </script>
</body>
</html>
"""


@router.post("/auth/login")
def dashboard_login(payload: DashboardLoginRequest, response: Response):
    settings = get_settings()
    scope = (payload.scope or "dashboard").strip().lower()
    if scope not in {"dashboard", "control"}:
        raise HTTPException(status_code=400, detail="Unsupported dashboard auth scope.")

    if scope == "control":
        is_valid = _password_matches(
            payload.password,
            _control_password(),
            settings.dashboard_control_password_hash.strip(),
        )
    else:
        is_valid = _password_matches(
            payload.password,
            _admin_password(),
            settings.dashboard_password_hash.strip(),
        )
        
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid password.")
        
    access_token = security.create_access_token(subject=scope)
    response.set_cookie(
        key=DASHBOARD_CONTROL_COOKIE if scope == "control" else DASHBOARD_AUTH_COOKIE,
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite="lax",
        path="/api/v1/dashboard",
    )
    return {"token": access_token, "scope": scope, "expires_in": settings.access_token_expire_minutes * 60}


@router.get("/settings-config", dependencies=[Depends(get_current_admin)])
def dashboard_settings_config(db: Session = Depends(get_db)):
    return _load_settings(db)


@router.put("/settings-config", dependencies=[Depends(get_current_admin)])
def update_dashboard_settings(
    payload: DashboardSettingsPayload,
    db: Session = Depends(get_db),
):
    return _save_settings(db, payload)


@router.get("/stats", dependencies=[Depends(get_current_admin)])
def stats_endpoint(db: Session = Depends(get_db)):
    return _safe_call("stats", get_stats, _fallback_stats(), db)


@router.get("/leads", dependencies=[Depends(get_current_admin)])
def leads_endpoint(db: Session = Depends(get_db)):
    return _safe_call("leads", get_leads_elite, [], db)


@router.get("/groups", dependencies=[Depends(get_current_admin)])
def groups_endpoint(db: Session = Depends(get_db)):
    logger.info("Accessing groups endpoint")
    return _safe_call("groups", get_groups_elite, [], db)


@router.get("/conversions", dependencies=[Depends(get_current_admin)])
def conversions_endpoint(db: Session = Depends(get_db)):
    return _safe_call("conversions", get_conversions_elite, [], db)


@router.get("/reseller-prospects", dependencies=[Depends(get_current_admin)])
def reseller_prospects_endpoint(db: Session = Depends(get_db)):
    return _safe_call("reseller-prospects", get_reseller_prospects_elite, [], db)


@router.get("/high-intent-buyers", dependencies=[Depends(get_current_admin)])
def high_intent_buyers_endpoint(db: Session = Depends(get_db)):
    """Show the 20 highest-intent buyers detected in the last 7 days."""
    return _safe_call("high-intent-buyers", get_high_intent_buyers_elite, [], db)


@router.get("/conversations", dependencies=[Depends(get_current_admin)])
def conversations_endpoint(username: str | None = None, db: Session = Depends(get_db)):
    return _safe_call("conversations", get_conversations_elite, [], db, username)


@router.get("/summary", response_model=DashboardSummary, dependencies=[Depends(get_current_admin)])
async def dashboard_summary_endpoint(db: Session = Depends(get_db)) -> DashboardSummary:
    return await _async_safe_call("summary", get_dashboard_summary, _fallback_summary(), db)


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
    return _render_page("targeting")


@router.get("/targeting", response_class=HTMLResponse)
def dashboard_targeting():
    return _render_page("targeting")


@router.get("/settings", response_class=HTMLResponse)
def dashboard_settings_page(request: Request):
    if not _settings_cookie_payload(request):
        return HTMLResponse(_build_settings_auth_gate_html(), status_code=401)
    return _render_page("settings")


@router.get("/styleguide", response_class=HTMLResponse)
def dashboard_styleguide_page():
    return _render_page("styleguide")
