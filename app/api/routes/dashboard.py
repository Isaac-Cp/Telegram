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
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import (
    get_conversations_elite,
    get_conversions_elite,
    get_dashboard_summary,
    get_groups_elite,
    get_leads_elite,
    get_reseller_prospects_elite,
    get_stats,
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
    notes: str = ""


def _default_settings() -> dict[str, Any]:
    return {
        "target_tags": ["iptv", "reseller", "trial users", "support issues"],
        "search_tags": ["buffering", "refund", "cheap iptv", "best provider"],
        "brand_tags": ["Streamexpert", "sales agent", "support crm"],
        "watch_terms": ["downtime", "ban", "competitor", "migration"],
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
        "notes": str(data.get("notes", base["notes"])).strip(),
    }


def _save_settings(payload: DashboardSettingsPayload) -> dict[str, Any]:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "target_tags": _normalize_tags(payload.target_tags),
        "search_tags": _normalize_tags(payload.search_tags),
        "brand_tags": _normalize_tags(payload.brand_tags),
        "watch_terms": _normalize_tags(payload.watch_terms),
        "notes": payload.notes.strip(),
    }
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _admin_password() -> str:
    return os.getenv("DASHBOARD_ADMIN_PASSWORD", "changeme")


def _mint_token() -> str:
    token = secrets.token_urlsafe(24)
    ACTIVE_TOKENS[token] = time.time() + TOKEN_TTL_SECONDS
    return token


def _require_dashboard_auth(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token.")
    token = authorization.split(" ", 1)[1].strip()
    expires_at = ACTIVE_TOKENS.get(token)
    if not expires_at:
        raise HTTPException(status_code=401, detail="Invalid authorization token.")
    if expires_at < time.time():
        ACTIVE_TOKENS.pop(token, None)
        raise HTTPException(status_code=401, detail="Authorization token expired.")


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
    return """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Revenue Command</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23081720'/%3E%3Cpath d='M16 42h8V28h-8zm12 0h8V20h-8zm12 0h8V32h-8z' fill='%2360a5fa'/%3E%3Cpath d='M18 18c8 2 13 1 18-2 3-2 6-4 10-4h2v7h-2c-2 0-4 1-6 2-6 4-13 6-22 3z' fill='%2334d399'/%3E%3C/svg%3E">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        ink: '#081120',
                        panel: '#0f172a',
                        panelSoft: '#131d33',
                        accent: '#3b82f6',
                        success: '#10b981',
                        warn: '#f59e0b',
                        danger: '#ef4444'
                    },
                    fontFamily: {
                        sans: ['Inter', 'sans-serif']
                    }
                }
            }
        }
    </script>
    <style>
        :root {
            color-scheme: dark;
        }
        body {
            min-height: 100vh;
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 22%),
                radial-gradient(circle at top right, rgba(6, 182, 212, 0.08), transparent 18%),
                linear-gradient(180deg, #050b16 0%, #070f1d 100%);
        }
        .shell-card {
            background:
                linear-gradient(180deg, rgba(30, 44, 68, 0.96), rgba(14, 22, 38, 0.98)),
                rgba(12, 20, 36, 0.94);
            border: 1px solid rgba(100, 116, 139, 0.16);
            box-shadow:
                inset 0 2px 2px rgba(255, 255, 255, 0.05),
                inset 0 -2px 3px rgba(15, 23, 42, 0.35),
                -10px -10px 24px rgba(56, 78, 112, 0.16),
                14px 18px 28px rgba(2, 6, 23, 0.34),
                0 2px 0 rgba(3, 7, 18, 0.72);
            backdrop-filter: blur(18px);
        }
        .metric-card {
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(145deg, rgba(37, 55, 84, 0.96), rgba(12, 20, 36, 0.98));
            border: 1px solid rgba(100, 116, 139, 0.18);
            box-shadow:
                inset 0 2px 3px rgba(255, 255, 255, 0.08),
                inset 0 -4px 8px rgba(15, 23, 42, 0.34),
                inset 1px 0 0 rgba(255, 255, 255, 0.03),
                inset -1px 0 0 rgba(255, 255, 255, 0.03),
                -10px -10px 26px rgba(56, 78, 112, 0.12),
                16px 20px 30px rgba(2, 6, 23, 0.34),
                0 3px 0 rgba(3, 7, 18, 0.78);
            transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
        }
        .metric-card::before {
            content: "";
            position: absolute;
            inset: 0 auto auto 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, rgba(96, 165, 250, 0.72), rgba(52, 211, 153, 0.40), transparent 78%);
        }
        .metric-card::after {
            content: "";
            position: absolute;
            inset: 10px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.04);
            pointer-events: none;
            opacity: 0.8;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            border-color: rgba(96, 165, 250, 0.35);
            box-shadow:
                inset 0 2px 4px rgba(255, 255, 255, 0.10),
                inset 0 -4px 8px rgba(15, 23, 42, 0.36),
                inset 1px 0 0 rgba(255, 255, 255, 0.04),
                inset -1px 0 0 rgba(255, 255, 255, 0.04),
                -10px -10px 26px rgba(56, 78, 112, 0.12),
                18px 24px 34px rgba(2, 6, 23, 0.34),
                0 3px 0 rgba(15, 23, 42, 0.68);
        }
        .nav-link {
            border: 1px solid transparent;
            transition: background 160ms ease, color 160ms ease, border-color 160ms ease;
        }
        .nav-link:hover {
            background: rgba(30, 41, 59, 0.82);
            border-color: rgba(96, 165, 250, 0.18);
            color: white;
        }
        .nav-link.active {
            background: linear-gradient(90deg, rgba(59, 130, 246, 0.18), rgba(59, 130, 246, 0.05));
            border-color: rgba(96, 165, 250, 0.28);
            color: white;
        }
        .pill {
            border: 1px solid rgba(100, 116, 139, 0.18);
            background: rgba(8, 15, 28, 0.88);
        }
        .mobile-topbar {
            transition: transform 220ms ease, opacity 180ms ease;
            will-change: transform;
        }
        .mobile-topbar.is-hidden {
            transform: translateY(-130%);
            opacity: 0.92;
        }
        .mobile-chip {
            border: 1px solid rgba(100, 116, 139, 0.18);
            background: rgba(8, 15, 28, 0.94);
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.03),
                0 10px 22px rgba(2, 6, 23, 0.24);
        }
        .card-icon-wrap {
            box-shadow:
                inset 0 2px 3px rgba(255, 255, 255, 0.10),
                inset 0 -3px 6px rgba(15, 23, 42, 0.26),
                0 12px 20px rgba(2, 6, 23, 0.22);
        }
        .theme-toggle {
            border: 1px solid rgba(100, 116, 139, 0.18);
            background: rgba(8, 15, 28, 0.92);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }
        .light-mode {
            background:
                radial-gradient(circle at top left, rgba(59, 130, 246, 0.10), transparent 24%),
                radial-gradient(circle at top right, rgba(16, 185, 129, 0.08), transparent 20%),
                linear-gradient(180deg, #eef3fb 0%, #e6edf8 100%);
            color: #0f172a;
        }
        .light-mode .shell-card,
        .light-mode .metric-card,
        .light-mode .pill,
        .light-mode .mobile-chip,
        .light-mode .theme-toggle {
            background: rgba(255, 255, 255, 0.9);
            border-color: rgba(148, 163, 184, 0.28);
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.7),
                0 18px 32px rgba(148, 163, 184, 0.18);
        }
        .light-mode .text-white,
        .light-mode .text-slate-100,
        .light-mode .text-slate-200,
        .light-mode .text-slate-300,
        .light-mode .text-slate-400,
        .light-mode .text-slate-500 {
            color: #334155 !important;
        }
        .light-mode .font-bold.text-white,
        .light-mode h1,
        .light-mode h2,
        .light-mode h3,
        .light-mode h4 {
            color: #0f172a !important;
        }
        .light-mode .bg-slate-900\\/70,
        .light-mode .bg-slate-900\\/75,
        .light-mode .bg-slate-900\\/80,
        .light-mode .bg-slate-950\\/70 {
            background: rgba(241, 245, 249, 0.92) !important;
        }
        .light-mode .bg-slate-800,
        .light-mode .bg-slate-950\\/60 {
            background: rgba(226, 232, 240, 0.9) !important;
        }
        .light-mode .border-white\\/10,
        .light-mode .border-white\\/8 {
            border-color: rgba(148, 163, 184, 0.24) !important;
        }
        .table-row {
            transition: background 140ms ease;
        }
        .table-row:hover {
            background: rgba(30, 41, 59, 0.34);
        }
        .tag-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 0.75rem;
            border-radius: 999px;
            background: rgba(30, 41, 59, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.14);
            color: #e2e8f0;
            font-size: 0.875rem;
            line-height: 1rem;
        }
        .tag-pill button {
            color: #94a3b8;
        }
        .tag-pill button:hover {
            color: white;
        }
        .stat-flash {
            text-shadow: 0 0 24px rgba(96, 165, 250, 0.35);
        }
        .section-hidden {
            display: none;
        }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-thumb { background: rgba(71, 85, 105, 0.72); border-radius: 999px; }
        ::-webkit-scrollbar-track { background: transparent; }
        aside::-webkit-scrollbar { width: 0; height: 0; }
        aside { scrollbar-width: none; -ms-overflow-style: none; }
    </style>
</head>
<body class="text-slate-100 antialiased">
    <div class="min-h-screen lg:grid lg:grid-cols-[290px_minmax(0,1fr)] lg:gap-6 lg:px-4 lg:pb-4">
        <aside class="hidden lg:flex lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:flex-col lg:self-start lg:overflow-y-auto lg:rounded-[28px] lg:border lg:border-white/8 lg:bg-slate-950/70 lg:p-5">
            <div class="shell-card rounded-2xl p-5">
                <div class="flex items-center gap-3">
                    <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/20 text-blue-300">
                        <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 13.5l8.25-8.25a2.121 2.121 0 013 0L22.5 13.5M6 10.5V21h12V10.5" />
                        </svg>
                    </div>
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-[0.22em] text-blue-300">Sales Agent</p>
                        <h1 class="text-lg font-bold text-white">Revenue Command</h1>
                    </div>
                </div>
                <p class="mt-4 text-sm leading-6 text-slate-400">Separate pages make it easier to shape each workflow cleanly around your sales operations.</p>
            </div>

            <nav class="mt-5 space-y-2 text-sm font-medium text-slate-400">
                <a class="nav-link __NAV_OVERVIEW__ flex items-center gap-3 rounded-2xl px-4 py-3" href="/api/v1/dashboard/overview">
                    <svg class="h-5 w-5 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7h18M3 12h18M3 17h18" />
                    </svg>
                    Overview
                </a>
                <a class="nav-link __NAV_ACTIVITY__ flex items-center gap-3 rounded-2xl px-4 py-3" href="/api/v1/dashboard/activity">
                    <svg class="h-5 w-5 text-emerald-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Activity Feed
                </a>
                <a class="nav-link __NAV_PIPELINE__ flex items-center gap-3 rounded-2xl px-4 py-3" href="/api/v1/dashboard/pipeline">
                    <svg class="h-5 w-5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7h16M7 12h10M10 17h4" />
                    </svg>
                    Pipeline
                </a>
                <a class="nav-link __NAV_WATCH__ flex items-center gap-3 rounded-2xl px-4 py-3" href="/api/v1/dashboard/watch">
                    <svg class="h-5 w-5 text-rose-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                    Competitor Watch
                </a>
                <a class="nav-link __NAV_SETTINGS__ flex items-center gap-3 rounded-2xl px-4 py-3" href="/api/v1/dashboard/settings">
                    <svg class="h-5 w-5 text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317a1.724 1.724 0 013.35 0l.296 1.189a1.724 1.724 0 001.637 1.28l1.246.052a1.724 1.724 0 011.676 2.206l-.354 1.197a1.724 1.724 0 00.49 1.77l.89.86a1.724 1.724 0 010 2.48l-.89.86a1.724 1.724 0 00-.49 1.77l.354 1.197a1.724 1.724 0 01-1.676 2.206l-1.246.052a1.724 1.724 0 00-1.637 1.28l-.296 1.189a1.724 1.724 0 01-3.35 0l-.296-1.189a1.724 1.724 0 00-1.637-1.28l-1.246-.052a1.724 1.724 0 01-1.676-2.206l.354-1.197a1.724 1.724 0 00-.49-1.77l-.89-.86a1.724 1.724 0 010-2.48l.89-.86a1.724 1.724 0 00.49-1.77l-.354-1.197A1.724 1.724 0 016.79 6.838l1.246-.052a1.724 1.724 0 001.637-1.28l.296-1.189z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Settings
                </a>
            </nav>

            <div class="mt-5 shell-card rounded-2xl p-5">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Sync status</p>
                        <p class="mt-2 text-sm font-semibold text-white">Auto-refresh every 5s</p>
                    </div>
                    <div class="h-3 w-3 rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(52,211,153,0.8)]"></div>
                </div>
                <p id="last-updated-desktop" class="mt-3 text-xs text-slate-400">Connecting...</p>
            </div>
        </aside>

        <main class="min-w-0 py-4 lg:px-0 lg:py-4">
            <nav id="mobile-topbar" class="mobile-topbar shell-card sticky top-0 z-30 w-full rounded-none border-x-0 px-4 py-3 sm:px-5 lg:hidden">
                <div class="flex items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-3">
                        <div class="card-icon-wrap flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-blue-500/15 text-blue-300">
                            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 13.5l8.25-8.25a2.121 2.121 0 013 0L22.5 13.5M6 10.5V21h12V10.5" />
                            </svg>
                        </div>
                        <div class="min-w-0">
                            <p class="text-[10px] font-semibold uppercase tracking-[0.18em] text-blue-300">Sales Agent</p>
                            <h1 class="truncate text-base font-bold leading-5 text-white">Revenue Command</h1>
                        </div>
                    </div>
                    <div class="flex shrink-0 items-center gap-2">
                        <button id="theme-toggle-mobile" class="theme-toggle rounded-xl px-3 py-2 text-[11px] font-semibold text-slate-200" type="button">Light</button>
                        <div class="mobile-chip rounded-xl px-3 py-1.5 text-right">
                            <p class="text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">Hot leads</p>
                            <p class="text-[14px] font-bold leading-4 text-white"><span id="stat-high-prob-mobile">0</span></p>
                        </div>
                    </div>
                </div>
                <div class="mt-3 grid grid-cols-5 gap-2 text-[12px] text-slate-300">
                    <a class="__NAV_OVERVIEW__ rounded-2xl border border-white/8 bg-slate-900/75 px-2 py-2 text-center font-medium" href="/api/v1/dashboard/overview">Overview</a>
                    <a class="__NAV_ACTIVITY__ rounded-2xl border border-white/8 bg-slate-900/75 px-2 py-2 text-center font-medium" href="/api/v1/dashboard/activity">Activity</a>
                    <a class="__NAV_PIPELINE__ rounded-2xl border border-white/8 bg-slate-900/75 px-2 py-2 text-center font-medium" href="/api/v1/dashboard/pipeline">Pipeline</a>
                    <a class="__NAV_WATCH__ rounded-2xl border border-white/8 bg-slate-900/75 px-2 py-2 text-center font-medium" href="/api/v1/dashboard/watch">Watch</a>
                    <a class="__NAV_SETTINGS__ rounded-2xl border border-white/8 bg-slate-900/75 px-2 py-2 text-center font-medium" href="/api/v1/dashboard/settings">Settings</a>
                </div>
                <div class="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                    <span>App navigation</span>
                    <p id="last-updated-mobile">Connecting...</p>
                </div>
            </nav>

            <div class="px-4 sm:px-6 lg:px-0">
            <header class="shell-card sticky top-4 z-20 mt-4 rounded-3xl px-4 py-3 sm:px-5 lg:mt-0">
                <div class="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                    <div>
                        <p id="page-eyebrow" class="text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-300">Overview</p>
                        <h2 id="page-title" class="mt-0.5 text-[1.35rem] font-bold tracking-tight text-white">Live agent dashboard</h2>
                        <p id="page-copy" class="mt-0.5 max-w-2xl text-[13px] leading-5 text-slate-400">Lead volume, outreach throughput, competitor signals, and ranked pipeline views in one control surface.</p>
                    </div>
                    <div class="flex flex-wrap items-center gap-1.5" id="header-pills">
                        <button id="theme-toggle-desktop" class="theme-toggle rounded-xl px-3 py-2 text-[11px] font-semibold text-slate-200" type="button">Light</button>
                        <div class="pill rounded-xl px-3 py-1.5">
                            <p class="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Hot leads</p>
                            <p class="text-[15px] font-bold text-white"><span id="stat-high-prob">0</span> active</p>
                        </div>
                        <div class="pill rounded-xl px-3 py-1.5">
                            <p class="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">Outbound</p>
                            <p class="text-[15px] font-bold text-white"><span id="stat-dms">0</span> DMs sent</p>
                        </div>
                    </div>
                </div>
            </header>

            <section id="page-overview" class="page-section mt-6 space-y-6">
                <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <article class="metric-card rounded-[26px] p-5">
                        <div class="flex items-start justify-between">
                            <div>
                                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Leads detected</p>
                                <p id="stat-leads" class="mt-4 text-4xl font-extrabold tracking-tight text-white">0</p>
                            </div>
                            <div class="card-icon-wrap rounded-2xl bg-blue-500/15 p-3 text-blue-300">
                                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                            </div>
                        </div>
                        <p class="mt-5 text-sm text-slate-400">Total prospects identified from joined groups and message analysis.</p>
                    </article>

                    <article class="metric-card rounded-[26px] p-5">
                        <div class="flex items-start justify-between">
                            <div>
                                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Conversion rate</p>
                                <p id="stat-conv-rate" class="mt-4 text-4xl font-extrabold tracking-tight text-white">0%</p>
                            </div>
                            <div class="card-icon-wrap rounded-2xl bg-emerald-500/15 p-3 text-emerald-300">
                                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 17l6-6 4 4 8-8" />
                                </svg>
                            </div>
                        </div>
                        <p class="mt-5 text-sm text-slate-400">Share of detected leads that have moved through to conversion.</p>
                    </article>

                    <article class="metric-card rounded-[26px] p-5">
                        <div class="flex items-start justify-between">
                            <div>
                                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Messages analyzed</p>
                                <p id="stat-messages" class="mt-4 text-4xl font-extrabold tracking-tight text-white">0</p>
                            </div>
                            <div class="card-icon-wrap rounded-2xl bg-violet-500/15 p-3 text-violet-300">
                                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4-.82L3 20l1.34-3.13A7.59 7.59 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                </svg>
                            </div>
                        </div>
                        <p class="mt-5 text-sm text-slate-400">Conversation volume scanned by the intelligence layer.</p>
                    </article>

                    <article class="metric-card rounded-[26px] p-5">
                        <div class="flex items-start justify-between">
                            <div>
                                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Groups joined</p>
                                <p id="stat-groups" class="mt-4 text-4xl font-extrabold tracking-tight text-white">0</p>
                            </div>
                            <div class="card-icon-wrap rounded-2xl bg-amber-500/15 p-3 text-amber-300">
                                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h7m-7 4h10M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z" />
                                </svg>
                            </div>
                        </div>
                        <p class="mt-5 text-sm text-slate-400">Coverage footprint across target communities and prospect sources.</p>
                    </article>
                </div>

                <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
                    <article class="shell-card rounded-3xl p-5 sm:p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Audience map</p>
                                <h3 class="mt-1 text-lg font-bold text-white">Influence distribution</h3>
                            </div>
                            <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Segmentation</span>
                        </div>
                        <div class="mt-6 h-[320px]">
                            <canvas id="influenceChart"></canvas>
                        </div>
                    </article>
                    <article class="shell-card rounded-3xl p-5 sm:p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Value forecast</p>
                                <h3 class="mt-1 text-lg font-bold text-white">LTV distribution</h3>
                            </div>
                            <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Revenue tiers</span>
                        </div>
                        <div class="mt-6 h-[320px]">
                            <canvas id="ltvChart"></canvas>
                        </div>
                    </article>
                </div>
            </section>

            <section id="page-activity" class="page-section section-hidden mt-6 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.85fr)]">
                <article class="shell-card overflow-hidden rounded-3xl">
                    <div class="border-b border-white/10 px-5 py-4 sm:px-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Live feed</p>
                                <h3 class="mt-1 text-lg font-bold text-white">Prospect and message activity</h3>
                            </div>
                            <div class="flex items-center gap-2 text-xs font-semibold text-emerald-300">
                                <span class="h-2 w-2 rounded-full bg-emerald-400"></span>
                                Streaming
                            </div>
                        </div>
                    </div>
                    <div id="activity-log" class="min-h-[560px] divide-y divide-white/8"></div>
                </article>

                <article class="space-y-4">
                    <div class="shell-card rounded-3xl p-5 sm:p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Execution safety</p>
                                <h3 class="mt-1 text-lg font-bold text-white">Account health</h3>
                            </div>
                            <span class="rounded-full bg-emerald-500/12 px-3 py-1 text-xs font-semibold text-emerald-300">Protected</span>
                        </div>
                        <div id="account-health" class="mt-5 space-y-4"></div>
                    </div>
                    <div class="metric-card rounded-[26px] p-5">
                        <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Operations note</p>
                        <h3 class="mt-3 text-lg font-bold text-white">Keep this page for fast scanning</h3>
                        <p class="mt-3 text-sm leading-6 text-slate-400">Breaking the dashboard into dedicated pages gives you more room for operational detail without crowding the overview.</p>
                    </div>
                </article>
            </section>

            <section id="page-pipeline" class="page-section section-hidden mt-6 space-y-6">
                <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
                    <article class="shell-card rounded-3xl p-5 sm:p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Pipeline</p>
                                <h3 class="mt-1 text-lg font-bold text-white">Hot opportunity queue</h3>
                            </div>
                            <div class="rounded-2xl bg-blue-500/15 px-3 py-2 text-xs font-semibold text-blue-200">Priority</div>
                        </div>
                        <div class="mt-6 rounded-3xl border border-blue-400/20 bg-blue-500/8 p-5">
                            <p class="text-sm text-slate-300">High-probability leads ready for the next sales action.</p>
                            <p class="mt-4 text-6xl font-extrabold tracking-tight text-white" id="pipeline-hot">0</p>
                        </div>
                        <div class="mt-5 grid grid-cols-2 gap-3">
                            <div class="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Outbound DMs</p>
                                <p class="mt-3 text-2xl font-bold text-white" id="pipeline-dms">0</p>
                            </div>
                            <div class="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                                <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Group coverage</p>
                                <p class="mt-3 text-2xl font-bold text-white" id="pipeline-groups">0</p>
                            </div>
                        </div>
                        <div class="mt-5 rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                            <div class="flex items-center justify-between text-sm">
                                <span class="text-slate-400">Conversion momentum</span>
                                <span id="pipeline-rate" class="font-semibold text-white">0%</span>
                            </div>
                            <div class="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
                                <div id="pipeline-rate-bar" class="h-full rounded-full bg-gradient-to-r from-blue-400 via-cyan-300 to-emerald-300" style="width:0%"></div>
                            </div>
                        </div>
                    </article>
                    <article class="shell-card rounded-3xl p-5 sm:p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Expansion</p>
                                <h3 class="mt-1 text-lg font-bold text-white">Reseller prospects</h3>
                            </div>
                            <span class="rounded-full bg-blue-500/12 px-3 py-1 text-xs font-semibold text-blue-200">Upside</span>
                        </div>
                        <div id="prospects-list" class="mt-5 space-y-3"></div>
                    </article>
                </div>

                <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    <article class="shell-card overflow-hidden rounded-3xl">
                        <div class="border-b border-white/10 px-5 py-4 sm:px-6">
                            <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Lead queue</p>
                            <h3 class="mt-1 text-lg font-bold text-white">Top leads by score</h3>
                        </div>
                        <div class="overflow-x-auto px-5 sm:px-6">
                            <table class="w-full min-w-[520px] text-left">
                                <thead>
                                    <tr class="border-b border-white/10 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                                        <th class="py-4 pr-4">Lead</th>
                                        <th class="py-4 pr-4">Score</th>
                                        <th class="py-4 pr-4">Stage</th>
                                        <th class="py-4 text-right">Last contact</th>
                                    </tr>
                                </thead>
                                <tbody id="leads-list"></tbody>
                            </table>
                        </div>
                    </article>

                    <article class="shell-card overflow-hidden rounded-3xl">
                        <div class="border-b border-white/10 px-5 py-4 sm:px-6">
                            <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Territory</p>
                            <h3 class="mt-1 text-lg font-bold text-white">Top groups by authority</h3>
                        </div>
                        <div class="overflow-x-auto px-5 sm:px-6">
                            <table class="w-full min-w-[520px] text-left">
                                <thead>
                                    <tr class="border-b border-white/10 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                                        <th class="py-4 pr-4">Group</th>
                                        <th class="py-4 pr-4">Authority</th>
                                        <th class="py-4 pr-4">Density</th>
                                        <th class="py-4 text-right">Status</th>
                                    </tr>
                                </thead>
                                <tbody id="groups-list"></tbody>
                            </table>
                        </div>
                    </article>
                </div>

                <article class="shell-card overflow-hidden rounded-3xl">
                    <div class="border-b border-white/10 px-5 py-4 sm:px-6">
                        <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Closed wins</p>
                        <h3 class="mt-1 text-lg font-bold text-white">Recent conversions</h3>
                    </div>
                    <div class="overflow-x-auto px-5 sm:px-6">
                        <table class="w-full min-w-[520px] text-left">
                            <thead>
                                <tr class="border-b border-white/10 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                                    <th class="py-4 pr-4">Lead</th>
                                    <th class="py-4 pr-4">Score</th>
                                    <th class="py-4 pr-4">Temperature</th>
                                    <th class="py-4 text-right">Last contact</th>
                                </tr>
                            </thead>
                            <tbody id="conversions-list"></tbody>
                        </table>
                    </div>
                </article>
            </section>

            <section id="page-watch" class="page-section section-hidden mt-6 space-y-6">
                <div class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.85fr)]">
                    <article class="shell-card overflow-hidden rounded-3xl">
                        <div class="border-b border-white/10 px-5 py-4 sm:px-6">
                            <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Market pressure</p>
                            <h3 class="mt-1 text-lg font-bold text-white">Competitor watch</h3>
                        </div>
                        <div class="overflow-x-auto px-5 sm:px-6">
                            <table class="w-full min-w-[560px] text-left">
                                <thead>
                                    <tr class="border-b border-white/10 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                                        <th class="py-4 pr-4">Competitor</th>
                                        <th class="py-4 pr-4">Weakness score</th>
                                        <th class="py-4 pr-4">Complaint volume</th>
                                        <th class="py-4 text-right">Updated</th>
                                    </tr>
                                </thead>
                                <tbody id="competitor-list"></tbody>
                            </table>
                        </div>
                    </article>
                    <article class="space-y-4">
                        <div class="metric-card rounded-[26px] p-5">
                            <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Monitoring focus</p>
                            <h3 class="mt-3 text-lg font-bold text-white">Watch terms</h3>
                            <div id="watch-terms-preview" class="mt-4 flex flex-wrap gap-2"></div>
                        </div>
                        <div class="metric-card rounded-[26px] p-5">
                            <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Brand context</p>
                            <h3 class="mt-3 text-lg font-bold text-white">Brand tags</h3>
                            <div id="brand-tags-preview" class="mt-4 flex flex-wrap gap-2"></div>
                        </div>
                    </article>
                </div>
            </section>

            <section id="page-settings" class="page-section section-hidden mt-6 space-y-6">
                <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <article class="metric-card rounded-[26px] p-5">
                        <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Workspace</p>
                        <p id="settings-target-count" class="mt-3 text-2xl font-bold text-white">0</p>
                        <p class="mt-2 text-sm text-slate-400">Target tags currently shaping discovery focus.</p>
                    </article>
                    <article class="metric-card rounded-[26px] p-5">
                        <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Discovery</p>
                        <p id="settings-search-count" class="mt-3 text-2xl font-bold text-white">0</p>
                        <p class="mt-2 text-sm text-slate-400">Search terms available for scanning and routing ideas.</p>
                    </article>
                    <article class="metric-card rounded-[26px] p-5">
                        <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Monitoring</p>
                        <p id="settings-watch-count" class="mt-3 text-2xl font-bold text-white">0</p>
                        <p class="mt-2 text-sm text-slate-400">Watch and brand terms currently configured.</p>
                    </article>
                </div>

                <div class="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
                    <article class="shell-card rounded-3xl p-5 sm:p-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Configuration</p>
                                <h3 class="mt-1 text-lg font-bold text-white">Dashboard settings</h3>
                            </div>
                            <div class="flex items-center gap-2">
                                <span id="settings-auth-badge" class="rounded-full bg-violet-500/12 px-3 py-1 text-xs font-semibold text-violet-200">Protected</span>
                                <button id="settings-signout" class="hidden rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-xs font-semibold text-slate-200" type="button">Sign out</button>
                            </div>
                        </div>

                        <div id="settings-auth" class="mt-6">
                            <div class="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                                <p class="text-sm text-slate-400">Sign in to edit target tags, search tags, brand tags, watch terms, and dashboard notes.</p>
                                <form id="settings-login-form" class="mt-4 space-y-4">
                                    <label class="block">
                                        <span class="mb-2 block text-sm font-medium text-slate-200">Admin password</span>
                                        <input id="settings-password" type="password" class="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-white outline-none focus:border-blue-400" placeholder="Enter dashboard password">
                                    </label>
                                    <button class="rounded-2xl bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-400" type="submit">Sign in</button>
                                    <p id="settings-login-error" class="text-sm text-rose-300"></p>
                                </form>
                            </div>
                        </div>

                        <div id="settings-editor" class="mt-6 hidden space-y-6">
                            <div class="grid grid-cols-1 gap-5 md:grid-cols-2">
                                <div class="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <p class="text-sm font-semibold text-white">Target tags</p>
                                            <p class="mt-1 text-xs text-slate-500">Lead themes and audiences.</p>
                                        </div>
                                        <span id="target_tags_count" class="rounded-full bg-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">0 tags</span>
                                    </div>
                                    <div class="mt-4 flex gap-2">
                                        <input id="target_tags_input" class="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none focus:border-blue-400" placeholder="Add target tag">
                                        <button class="rounded-2xl bg-slate-800 px-4 py-3 text-xs font-semibold text-slate-200" data-add-tag="target_tags" type="button">Add</button>
                                    </div>
                                    <div id="target_tags" class="mt-4 flex flex-wrap gap-2"></div>
                                </div>
                                <div class="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <p class="text-sm font-semibold text-white">Search tags</p>
                                            <p class="mt-1 text-xs text-slate-500">Discovery terms and query ideas.</p>
                                        </div>
                                        <span id="search_tags_count" class="rounded-full bg-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">0 tags</span>
                                    </div>
                                    <div class="mt-4 flex gap-2">
                                        <input id="search_tags_input" class="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none focus:border-blue-400" placeholder="Add search tag">
                                        <button class="rounded-2xl bg-slate-800 px-4 py-3 text-xs font-semibold text-slate-200" data-add-tag="search_tags" type="button">Add</button>
                                    </div>
                                    <div id="search_tags" class="mt-4 flex flex-wrap gap-2"></div>
                                </div>
                                <div class="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <p class="text-sm font-semibold text-white">Brand tags</p>
                                            <p class="mt-1 text-xs text-slate-500">Terms to align the dashboard with your brand context.</p>
                                        </div>
                                        <span id="brand_tags_count" class="rounded-full bg-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">0 tags</span>
                                    </div>
                                    <div class="mt-4 flex gap-2">
                                        <input id="brand_tags_input" class="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none focus:border-blue-400" placeholder="Add brand tag">
                                        <button class="rounded-2xl bg-slate-800 px-4 py-3 text-xs font-semibold text-slate-200" data-add-tag="brand_tags" type="button">Add</button>
                                    </div>
                                    <div id="brand_tags" class="mt-4 flex flex-wrap gap-2"></div>
                                </div>
                                <div class="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                                    <div class="flex items-center justify-between">
                                        <div>
                                            <p class="text-sm font-semibold text-white">Watch terms</p>
                                            <p class="mt-1 text-xs text-slate-500">Signals to track in market watch.</p>
                                        </div>
                                        <span id="watch_terms_count" class="rounded-full bg-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">0 tags</span>
                                    </div>
                                    <div class="mt-4 flex gap-2">
                                        <input id="watch_terms_input" class="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none focus:border-blue-400" placeholder="Add watch term">
                                        <button class="rounded-2xl bg-slate-800 px-4 py-3 text-xs font-semibold text-slate-200" data-add-tag="watch_terms" type="button">Add</button>
                                    </div>
                                    <div id="watch_terms" class="mt-4 flex flex-wrap gap-2"></div>
                                </div>
                            </div>

                            <div class="rounded-3xl border border-white/10 bg-slate-900/70 p-5">
                                <label class="block">
                                    <span class="mb-2 block text-sm font-medium text-white">Notes</span>
                                    <textarea id="settings-notes" class="min-h-[160px] w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none focus:border-blue-400"></textarea>
                                </label>
                            </div>

                            <div class="flex flex-wrap items-center gap-3">
                                <button id="settings-save" class="rounded-2xl bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-400" type="button">Save settings</button>
                                <button id="settings-refresh" class="rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm font-semibold text-slate-200" type="button">Reload</button>
                                <p id="settings-status" class="text-sm text-slate-400"></p>
                            </div>
                        </div>
                    </article>

                    <article class="space-y-4">
                        <div class="metric-card rounded-[26px] p-5">
                            <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">What this controls</p>
                            <h3 class="mt-3 text-lg font-bold text-white">Editable dashboard inputs</h3>
                            <p class="mt-3 text-sm leading-6 text-slate-400">Use these lists to keep your targeting, search language, and brand context adjustable without hand-editing the dashboard code each time.</p>
                        </div>
                        <div class="metric-card rounded-[26px] p-5">
                            <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Live preview</p>
                            <h3 class="mt-3 text-lg font-bold text-white">Current tag summary</h3>
                            <div id="settings-preview" class="mt-4 space-y-3 text-sm text-slate-300"></div>
                        </div>
                        <div class="metric-card rounded-[26px] p-5">
                            <p class="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Security</p>
                            <h3 class="mt-3 text-lg font-bold text-white">Protected editor</h3>
                            <p class="mt-3 text-sm leading-6 text-slate-400">Settings are locked behind the dashboard admin password and persisted locally for reuse across sessions.</p>
                        </div>
                    </article>
                </div>
            </section>
            </div>
        </main>
    </div>

    <script>
        const ACTIVE_PAGE = "__ACTIVE_PAGE__";
        const PAGE_META = {
            overview: {
                eyebrow: "Overview",
                title: "Live agent dashboard",
                copy: "Lead volume, outreach throughput, competitor signals, and ranked pipeline views in one control surface."
            },
            activity: {
                eyebrow: "Activity Feed",
                title: "Real-time operations stream",
                copy: "A dedicated page for message flow, recent interactions, and delivery safety."
            },
            pipeline: {
                eyebrow: "Pipeline",
                title: "Lead progression and opportunity depth",
                copy: "Separate pipeline views make it easier to tune ranking, conversions, and expansion plays."
            },
            watch: {
                eyebrow: "Competitor Watch",
                title: "Market pressure and brand context",
                copy: "Use the watch page to track competitive signals and the terms that shape your response."
            },
            settings: {
                eyebrow: "Settings",
                title: "Editable dashboard controls",
                copy: "Sign in to edit tags and dashboard-facing configuration without reopening the code every time."
            }
        };

        let influenceChart;
        let ltvChart;
        let dashboardSettings = null;

        function flashMetric(id, value, suffix = '') {
            const el = document.getElementById(id);
            if (!el) return;
            const nextText = `${value}${suffix}`;
            if (el.textContent !== nextText) {
                el.textContent = nextText;
                el.classList.add('stat-flash');
                setTimeout(() => el.classList.remove('stat-flash'), 900);
            }
        }

        function clampPercent(value) {
            const numeric = Number(value) || 0;
            return Math.max(0, Math.min(100, numeric));
        }

        function formatDate(value) {
            if (!value) return 'No contact';
            const parsed = new Date(value);
            if (Number.isNaN(parsed.getTime())) return String(value);
            return parsed.toLocaleDateString();
        }

        function renderActivity(items) {
            const host = document.getElementById('activity-log');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<div class="px-6 py-16 text-center text-sm text-slate-500">No recent bot activity yet.</div>';
                return;
            }

            host.innerHTML = items.map((item) => {
                const typeLabel = (item.type || 'activity').toUpperCase();
                const text = item.text || 'No message body';
                const accent = /need|help|buy|price|urgent/i.test(text) ? 'text-emerald-300 bg-emerald-500/10' : 'text-blue-300 bg-blue-500/10';
                return `
                    <div class="flex items-start justify-between gap-4 px-5 py-4 sm:px-6">
                        <div class="flex min-w-0 items-start gap-4">
                            <div class="${accent} flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-xs font-bold">
                                ${typeLabel.slice(0, 1)}
                            </div>
                            <div class="min-w-0">
                                <div class="flex flex-wrap items-center gap-2">
                                    <p class="text-sm font-semibold text-white">@${item.user || 'unknown'}</p>
                                    <span class="rounded-full bg-slate-800 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">${typeLabel}</span>
                                </div>
                                <p class="mt-2 text-sm leading-6 text-slate-400">${text}</p>
                            </div>
                        </div>
                        <p class="shrink-0 text-xs font-medium text-slate-500">${item.time || '--:--:--'}</p>
                    </div>
                `;
            }).join('');
        }

        function renderHealth(items) {
            const host = document.getElementById('account-health');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<div class="rounded-2xl border border-white/10 bg-slate-900/70 p-4 text-sm text-slate-500">No Telegram account records available yet.</div>';
                return;
            }

            host.innerHTML = items.map((item) => {
                const replyCap = Math.max(0, Math.min(100, ((item.replies_left || 0) / 5) * 100));
                const dmCap = Math.max(0, Math.min(100, ((item.dms_left || 0) / 10) * 100));
                const statusClass = item.status === 'active'
                    ? 'bg-emerald-500/12 text-emerald-300'
                    : 'bg-rose-500/12 text-rose-300';

                return `
                    <div class="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                        <div class="flex items-center justify-between gap-3">
                            <div>
                                <p class="text-sm font-semibold text-white">${item.phone || 'Unknown account'}</p>
                                <p class="mt-1 text-xs text-slate-500">Operational limits and daily room</p>
                            </div>
                            <span class="${statusClass} rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]">${item.status || 'unknown'}</span>
                        </div>
                        <div class="mt-4 space-y-3">
                            <div>
                                <div class="mb-1 flex items-center justify-between text-xs text-slate-400">
                                    <span>Replies left</span>
                                    <span>${item.replies_left ?? 0}/5</span>
                                </div>
                                <div class="h-2 overflow-hidden rounded-full bg-slate-800">
                                    <div class="h-full rounded-full bg-blue-400" style="width:${replyCap}%"></div>
                                </div>
                            </div>
                            <div>
                                <div class="mb-1 flex items-center justify-between text-xs text-slate-400">
                                    <span>DMs left</span>
                                    <span>${item.dms_left ?? 0}/10</span>
                                </div>
                                <div class="h-2 overflow-hidden rounded-full bg-slate-800">
                                    <div class="h-full rounded-full bg-emerald-400" style="width:${dmCap}%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function renderCompetitors(items) {
            const host = document.getElementById('competitor-list');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<tr><td colspan="4" class="py-12 text-center text-sm text-slate-500">No competitor insight records yet.</td></tr>';
                return;
            }

            host.innerHTML = items.map((item) => `
                <tr class="table-row border-b border-white/6 text-sm text-slate-300">
                    <td class="py-4 pr-4 font-semibold text-white">${item.name || 'Unknown'}</td>
                    <td class="py-4 pr-4">
                        <span class="rounded-full bg-rose-500/12 px-3 py-1 text-xs font-semibold text-rose-300">${item.score ?? 0}</span>
                    </td>
                    <td class="py-4 pr-4 text-slate-400">${item.complaints ?? 0} complaint signals</td>
                    <td class="py-4 text-right text-xs text-slate-500">${new Date().toLocaleDateString()}</td>
                </tr>
            `).join('');
        }

        function renderLeads(items) {
            const host = document.getElementById('leads-list');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<tr><td colspan="4" class="py-12 text-center text-sm text-slate-500">No lead rankings available yet.</td></tr>';
                return;
            }

            host.innerHTML = items.slice(0, 8).map((item) => `
                <tr class="table-row border-b border-white/6 text-sm text-slate-300">
                    <td class="py-4 pr-4 font-semibold text-white">@${item.username || 'unknown'}</td>
                    <td class="py-4 pr-4"><span class="rounded-full bg-blue-500/12 px-3 py-1 text-xs font-semibold text-blue-200">${item.score ?? 0}</span></td>
                    <td class="py-4 pr-4 text-slate-400">${item.status || 'unknown'}</td>
                    <td class="py-4 text-right text-xs text-slate-500">${formatDate(item.last_contact)}</td>
                </tr>
            `).join('');
        }

        function renderGroups(items) {
            const host = document.getElementById('groups-list');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<tr><td colspan="4" class="py-12 text-center text-sm text-slate-500">No joined groups available yet.</td></tr>';
                return;
            }

            host.innerHTML = items.slice(0, 8).map((item) => `
                <tr class="table-row border-b border-white/6 text-sm text-slate-300">
                    <td class="py-4 pr-4 font-semibold text-white">${item.name || 'Unnamed group'}</td>
                    <td class="py-4 pr-4"><span class="rounded-full bg-emerald-500/12 px-3 py-1 text-xs font-semibold text-emerald-300">${item.score ?? 0}</span></td>
                    <td class="py-4 pr-4 text-slate-400">${item.density ?? 0}</td>
                    <td class="py-4 text-right text-xs uppercase tracking-[0.18em] text-slate-500">${item.status || 'unknown'}</td>
                </tr>
            `).join('');
        }

        function renderConversions(items) {
            const host = document.getElementById('conversions-list');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<tr><td colspan="4" class="py-12 text-center text-sm text-slate-500">No conversions recorded yet.</td></tr>';
                return;
            }

            host.innerHTML = items.slice(0, 8).map((item) => `
                <tr class="table-row border-b border-white/6 text-sm text-slate-300">
                    <td class="py-4 pr-4 font-semibold text-white">@${item.username || 'unknown'}</td>
                    <td class="py-4 pr-4"><span class="rounded-full bg-emerald-500/12 px-3 py-1 text-xs font-semibold text-emerald-300">${item.score ?? 0}</span></td>
                    <td class="py-4 pr-4 text-slate-400">${item.temperature || 'n/a'}</td>
                    <td class="py-4 text-right text-xs text-slate-500">${formatDate(item.last_contact)}</td>
                </tr>
            `).join('');
        }

        function renderProspects(items) {
            const host = document.getElementById('prospects-list');
            if (!host) return;
            if (!items.length) {
                host.innerHTML = '<div class="rounded-2xl border border-white/10 bg-slate-900/70 p-4 text-sm text-slate-500">No reseller prospects identified yet.</div>';
                return;
            }

            host.innerHTML = items.slice(0, 6).map((item) => `
                <div class="rounded-2xl border border-white/10 bg-slate-900/70 p-4">
                    <div class="flex items-center justify-between gap-3">
                        <div>
                            <p class="text-sm font-semibold text-white">@${item.username || 'unknown'}</p>
                            <p class="mt-1 text-xs text-slate-500">${item.level || 'Prospect'}</p>
                        </div>
                        <span class="rounded-full bg-amber-500/12 px-3 py-1 text-xs font-semibold text-amber-300">${item.score ?? 0}</span>
                    </div>
                    <p class="mt-3 text-xs text-slate-500">Updated ${formatDate(item.last_updated)}</p>
                </div>
            `).join('');
        }

        function renderTagPreview(id, items) {
            const host = document.getElementById(id);
            if (!host) return;
            host.innerHTML = items.length
                ? items.map((item) => `<span class="tag-pill">${item}</span>`).join('')
                : '<span class="text-sm text-slate-500">No terms set yet.</span>';
        }

        function updateCharts(data) {
            const influenceCanvas = document.getElementById('influenceChart');
            if (influenceCanvas) {
                const influenceCtx = influenceCanvas.getContext('2d');
                const influenceValues = [
                    data.influence_distribution?.leader || 0,
                    data.influence_distribution?.power_user || 0,
                    data.influence_distribution?.regular || 0
                ];

                if (influenceChart) {
                    influenceChart.data.datasets[0].data = influenceValues;
                    influenceChart.update();
                } else {
                    influenceChart = new Chart(influenceCtx, {
                        type: 'doughnut',
                        data: {
                            labels: ['Leaders', 'Power users', 'Regulars'],
                            datasets: [{
                                data: influenceValues,
                                backgroundColor: ['#3b82f6', '#22c55e', '#64748b'],
                                borderWidth: 0,
                                hoverOffset: 10
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            cutout: '72%',
                            plugins: {
                                legend: {
                                    position: 'bottom',
                                    labels: {
                                        color: '#cbd5e1',
                                        padding: 18,
                                        usePointStyle: true,
                                        font: { family: 'Inter', size: 11, weight: '600' }
                                    }
                                }
                            }
                        }
                    });
                }
            }

            const ltvCanvas = document.getElementById('ltvChart');
            if (ltvCanvas) {
                const ltvCtx = ltvCanvas.getContext('2d');
                const labels = Object.keys(data.ltv_distribution || {}).map((key) => key.replace(/_/g, ' '));
                const values = Object.values(data.ltv_distribution || {});

                if (ltvChart) {
                    ltvChart.data.labels = labels;
                    ltvChart.data.datasets[0].data = values;
                    ltvChart.update();
                } else {
                    ltvChart = new Chart(ltvCtx, {
                        type: 'bar',
                        data: {
                            labels,
                            datasets: [{
                                label: 'Lead count',
                                data: values,
                                backgroundColor: ['#60a5fa', '#34d399', '#f59e0b', '#f472b6', '#a78bfa'],
                                borderRadius: 10,
                                maxBarThickness: 38
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    grid: { color: 'rgba(148, 163, 184, 0.12)' },
                                    ticks: { color: '#cbd5e1' }
                                },
                                x: {
                                    grid: { display: false },
                                    ticks: { color: '#cbd5e1' }
                                }
                            }
                        }
                    });
                }
            }
        }

        function applyPageMeta() {
            const meta = PAGE_META[ACTIVE_PAGE] || PAGE_META.overview;
            document.getElementById('page-eyebrow').textContent = meta.eyebrow;
            document.getElementById('page-title').textContent = meta.title;
            document.getElementById('page-copy').textContent = meta.copy;
            document.querySelectorAll('.page-section').forEach((section) => section.classList.add('section-hidden'));
            const activeSection = document.getElementById(`page-${ACTIVE_PAGE}`);
            if (activeSection) {
                activeSection.classList.remove('section-hidden');
            }
        }

        function updateLastSync(text) {
            const desktop = document.getElementById('last-updated-desktop');
            const mobile = document.getElementById('last-updated-mobile');
            if (desktop) desktop.textContent = text;
            if (mobile) mobile.textContent = text;
        }

        async function updateDashboard() {
            try {
                const [statsResponse, leadsResponse, groupsResponse, conversionsResponse, prospectsResponse, settingsResponse] = await Promise.all([
                    fetch('/api/v1/dashboard/stats'),
                    fetch('/api/v1/dashboard/leads'),
                    fetch('/api/v1/dashboard/groups'),
                    fetch('/api/v1/dashboard/conversions'),
                    fetch('/api/v1/dashboard/reseller-prospects'),
                    fetch('/api/v1/dashboard/settings-config')
                ]);
                const responses = [statsResponse, leadsResponse, groupsResponse, conversionsResponse, prospectsResponse, settingsResponse];
                if (responses.some((response) => !response.ok)) {
                    throw new Error('Failed to load dashboard data');
                }

                const [data, leads, groups, conversions, prospects, settings] = await Promise.all(
                    responses.map((response) => response.json())
                );
                dashboardSettings = settings;
                const conversionRate = Number(data.conversion_rate || 0).toFixed(2);
                const hotLeads = data.high_prob_leads || 0;
                const dmCount = data.dms_sent || 0;

                flashMetric('stat-leads', data.leads_detected || 0);
                flashMetric('stat-conv-rate', conversionRate, '%');
                flashMetric('stat-messages', data.messages_analyzed || 0);
                flashMetric('stat-groups', data.total_groups_joined || 0);
                flashMetric('stat-high-prob', hotLeads);
                flashMetric('stat-high-prob-mobile', hotLeads);
                flashMetric('stat-dms', dmCount);
                flashMetric('pipeline-hot', hotLeads);
                flashMetric('pipeline-dms', dmCount);
                flashMetric('pipeline-groups', data.total_groups_joined || 0);
                flashMetric('pipeline-rate', conversionRate, '%');
                const rateBar = document.getElementById('pipeline-rate-bar');
                if (rateBar) rateBar.style.width = `${clampPercent(conversionRate)}%`;
                updateLastSync(`Last sync: ${new Date().toLocaleTimeString()}`);

                renderActivity(data.activity_log || []);
                renderHealth(data.account_health || []);
                renderCompetitors(data.competitor_stats || []);
                renderLeads(leads || []);
                renderGroups(groups || []);
                renderConversions(conversions || []);
                renderProspects(prospects || []);
                renderTagPreview('watch-terms-preview', settings.watch_terms || []);
                renderTagPreview('brand-tags-preview', settings.brand_tags || []);
                updateCharts(data);

                if (ACTIVE_PAGE === 'settings') {
                    applySettingsData(settings);
                }
            } catch (error) {
                console.error('Dashboard sync failed:', error);
                updateLastSync('Unable to refresh dashboard right now');
            }
        }

        function getStoredToken() {
            return localStorage.getItem('dashboard_admin_token') || '';
        }

        function setStoredToken(token) {
            localStorage.setItem('dashboard_admin_token', token);
        }

        function createTagMarkup(key, item, index) {
            return `
                <span class="tag-pill">
                    <span>${item}</span>
                    <button type="button" data-remove-tag="${key}" data-index="${index}" aria-label="Remove tag">×</button>
                </span>
            `;
        }

        function applySettingsData(settings) {
            dashboardSettings = settings;
            ['target_tags', 'search_tags', 'brand_tags', 'watch_terms'].forEach((key) => {
                const host = document.getElementById(key);
                if (!host) return;
                const items = settings[key] || [];
                const countEl = document.getElementById(`${key}_count`);
                if (countEl) countEl.textContent = `${items.length} tag${items.length === 1 ? '' : 's'}`;
                host.innerHTML = items.length
                    ? items.map((item, index) => createTagMarkup(key, item, index)).join('')
                    : '<span class="text-sm text-slate-500">Nothing added yet.</span>';
                const input = document.getElementById(`${key}_input`);
                if (input) input.value = '';
            });
            const notes = document.getElementById('settings-notes');
            if (notes) notes.value = settings.notes || '';

            const targetCount = document.getElementById('settings-target-count');
            const searchCount = document.getElementById('settings-search-count');
            const watchCount = document.getElementById('settings-watch-count');
            if (targetCount) targetCount.textContent = String((settings.target_tags || []).length);
            if (searchCount) searchCount.textContent = String((settings.search_tags || []).length);
            if (watchCount) watchCount.textContent = String((settings.watch_terms || []).length + (settings.brand_tags || []).length);

            const preview = document.getElementById('settings-preview');
            if (preview) {
                preview.innerHTML = `
                    <div><span class="text-slate-500">Target tags:</span> ${(settings.target_tags || []).length}</div>
                    <div><span class="text-slate-500">Search tags:</span> ${(settings.search_tags || []).length}</div>
                    <div><span class="text-slate-500">Brand tags:</span> ${(settings.brand_tags || []).length}</div>
                    <div><span class="text-slate-500">Watch terms:</span> ${(settings.watch_terms || []).length}</div>
                `;
            }
        }

        function collectSettingsPayload() {
            return {
                target_tags: dashboardSettings?.target_tags || [],
                search_tags: dashboardSettings?.search_tags || [],
                brand_tags: dashboardSettings?.brand_tags || [],
                watch_terms: dashboardSettings?.watch_terms || [],
                notes: document.getElementById('settings-notes')?.value || ''
            };
        }

        async function loadProtectedSettings() {
            const token = getStoredToken();
            if (!token) return false;
            const response = await fetch('/api/v1/dashboard/settings-config', {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (!response.ok) {
                return false;
            }
            const data = await response.json();
            document.getElementById('settings-auth').classList.add('hidden');
            document.getElementById('settings-editor').classList.remove('hidden');
            const badge = document.getElementById('settings-auth-badge');
            const signout = document.getElementById('settings-signout');
            if (badge) badge.textContent = 'Authenticated';
            if (signout) signout.classList.remove('hidden');
            applySettingsData(data);
            return true;
        }

        function wireSettingsEvents() {
            const form = document.getElementById('settings-login-form');
            if (form) {
                form.addEventListener('submit', async (event) => {
                    event.preventDefault();
                    const password = document.getElementById('settings-password').value;
                    const errorEl = document.getElementById('settings-login-error');
                    errorEl.textContent = '';
                    const response = await fetch('/api/v1/dashboard/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password })
                    });
                    if (!response.ok) {
                        errorEl.textContent = 'Unable to sign in with that password.';
                        return;
                    }
                    const data = await response.json();
                    setStoredToken(data.token);
                    await loadProtectedSettings();
                });
            }

            document.querySelectorAll('[data-add-tag]').forEach((button) => {
                button.addEventListener('click', () => {
                    const key = button.getAttribute('data-add-tag');
                    const input = document.getElementById(`${key}_input`);
                    const next = input ? input.value.trim() : '';
                    if (!next || !dashboardSettings) return;
                    dashboardSettings[key] = [...(dashboardSettings[key] || []), next].filter(Boolean);
                    applySettingsData(dashboardSettings);
                });
            });

            document.addEventListener('click', (event) => {
                const target = event.target;
                if (!(target instanceof HTMLElement)) return;
                const key = target.getAttribute('data-remove-tag');
                const index = Number(target.getAttribute('data-index'));
                if (!key || Number.isNaN(index) || !dashboardSettings) return;
                dashboardSettings[key] = (dashboardSettings[key] || []).filter((_, itemIndex) => itemIndex !== index);
                applySettingsData(dashboardSettings);
            });

            const saveButton = document.getElementById('settings-save');
            if (saveButton) {
                saveButton.addEventListener('click', async () => {
                    const token = getStoredToken();
                    const status = document.getElementById('settings-status');
                    status.textContent = 'Saving...';
                    const response = await fetch('/api/v1/dashboard/settings-config', {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: `Bearer ${token}`
                        },
                        body: JSON.stringify(collectSettingsPayload())
                    });
                    if (!response.ok) {
                        status.textContent = 'Save failed.';
                        return;
                    }
                    const data = await response.json();
                    applySettingsData(data);
                    renderTagPreview('watch-terms-preview', data.watch_terms || []);
                    renderTagPreview('brand-tags-preview', data.brand_tags || []);
                    status.textContent = 'Saved.';
                });
            }

            const refreshButton = document.getElementById('settings-refresh');
            if (refreshButton) {
                refreshButton.addEventListener('click', async () => {
                    const ok = await loadProtectedSettings();
                    document.getElementById('settings-status').textContent = ok ? 'Reloaded.' : 'Unable to reload.';
                });
            }

            const signoutButton = document.getElementById('settings-signout');
            if (signoutButton) {
                signoutButton.addEventListener('click', () => {
                    localStorage.removeItem('dashboard_admin_token');
                    document.getElementById('settings-auth').classList.remove('hidden');
                    document.getElementById('settings-editor').classList.add('hidden');
                    document.getElementById('settings-status').textContent = 'Signed out.';
                    const badge = document.getElementById('settings-auth-badge');
                    if (badge) badge.textContent = 'Protected';
                    signoutButton.classList.add('hidden');
                });
            }
        }

        function decorateActiveNav() {
            const map = {
                overview: '__NAV_OVERVIEW__',
                activity: '__NAV_ACTIVITY__',
                pipeline: '__NAV_PIPELINE__',
                watch: '__NAV_WATCH__',
                settings: '__NAV_SETTINGS__'
            };
            const token = map[ACTIVE_PAGE];
            document.querySelectorAll(`.${token}`).forEach((el) => {
                el.classList.add('active');
            });
        }

        function applyTheme(theme) {
            document.body.classList.toggle('light-mode', theme === 'light');
            document.documentElement.classList.toggle('dark', theme !== 'light');
            const nextLabel = theme === 'light' ? 'Dark' : 'Light';
            const mobileToggle = document.getElementById('theme-toggle-mobile');
            const desktopToggle = document.getElementById('theme-toggle-desktop');
            if (mobileToggle) mobileToggle.textContent = nextLabel;
            if (desktopToggle) desktopToggle.textContent = nextLabel;
            localStorage.setItem('dashboard_theme', theme);
        }

        function wireThemeToggle() {
            const stored = localStorage.getItem('dashboard_theme') || 'dark';
            applyTheme(stored);
            ['theme-toggle-mobile', 'theme-toggle-desktop'].forEach((id) => {
                const button = document.getElementById(id);
                if (!button) return;
                button.addEventListener('click', () => {
                    const current = document.body.classList.contains('light-mode') ? 'light' : 'dark';
                    applyTheme(current === 'light' ? 'dark' : 'light');
                });
            });
        }

        async function init() {
            decorateActiveNav();
            applyPageMeta();
            wireSettingsEvents();
            wireThemeToggle();
            let lastScrollY = window.scrollY;
            const mobileTopbar = document.getElementById('mobile-topbar');
            if (mobileTopbar) {
                window.addEventListener('scroll', () => {
                    const currentScrollY = window.scrollY;
                    const scrollingDown = currentScrollY > lastScrollY;
                    const farEnough = currentScrollY > 72;
                    if (scrollingDown && farEnough) {
                        mobileTopbar.classList.add('is-hidden');
                    } else {
                        mobileTopbar.classList.remove('is-hidden');
                    }
                    lastScrollY = currentScrollY;
                }, { passive: true });
            }
            await updateDashboard();
            if (ACTIVE_PAGE === 'settings') {
                await loadProtectedSettings();
            }
            setInterval(updateDashboard, 5000);
        }

        init();
    </script>
</body>
</html>
""".replace("__ACTIVE_PAGE__", active_page).replace("__NAV_OVERVIEW__", "nav-overview").replace("__NAV_ACTIVITY__", "nav-activity").replace("__NAV_PIPELINE__", "nav-pipeline").replace("__NAV_WATCH__", "nav-watch").replace("__NAV_SETTINGS__", "nav-settings")


def _render_page(active_page: str) -> HTMLResponse:
    return HTMLResponse(_build_dashboard_html(active_page))


@router.post("/auth/login")
def dashboard_login(payload: DashboardLoginRequest):
    if payload.password != _admin_password():
        raise HTTPException(status_code=401, detail="Invalid password.")
    return {"token": _mint_token(), "expires_in": TOKEN_TTL_SECONDS}


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


@router.get("/conversations")
def conversations_endpoint(db: Session = Depends(get_db)):
    return _safe_call("conversations", get_conversations_elite, [], db)


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


@router.get("/settings", response_class=HTMLResponse)
def dashboard_settings_page():
    return _render_page("settings")
