# Streamexpert Support CRM

Compliant Telegram IPTV support and CRM scaffold built for opt-in workflows only. The platform assumes users start the conversation themselves through a Telegram bot or other approved intake channel, after which support teams can triage requests, store consent, schedule follow-ups, and review AI-generated reply drafts.

## What This Scaffold Includes

- FastAPI service layout with versioned API routes
- SQLAlchemy models and Alembic migration scaffold for contacts, consents, conversations, tickets, messages, follow-up jobs, engagement profiles, activity events, and daily metrics
- Redis integration for job queue handoff
- APScheduler jobs for consent-safe reminders, engagement scoring, stale conversation handling, and daily metrics snapshots
- Documentation for the compliant system prompt and the opt-in workflow design

## Quick Start

1. Copy `.env.example` to `.env` and fill in the values you need.
2. Start the full stack with Docker:

```bash
docker compose up -d
```

This starts `api`, `postgres`, and `redis` together. The `api` service runs both the FastAPI website and the Telegram bot background tasks in the same process, so the bot and dashboard start together.

The compose file configures `REDIS_URL=redis://redis:6379/0` for the API service and persists Redis data in `redis_data`.

3. Install the app:

```bash
pip install -e .
```

4. Run migrations:

```bash
alembic upgrade head
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

6. Open the local dashboard overview at:

```bash
http://localhost:8000/api/v1/dashboard/overview
```

7. Run the dashboard visual checks:

```bash
npm install
npm run test:dashboard:visual:update
npm run test:dashboard:visual
```

## Deployment Notes

This app is a long-running FastAPI service with APScheduler jobs and a Telethon Telegram client. Do not deploy it to Vercel or another serverless function platform for bot work; serverless instances are short-lived and will not keep the Telegram listener/scheduler running.

For Render, use an always-on paid service for production bot work. Render Free web services are acceptable for previewing the dashboard, but they spin down when idle and are not reliable for a Telegram listener or scheduled background jobs. If you only want to run the dashboard, set `TELEGRAM_ENABLED=false`. If you want the bot to run, set `TELEGRAM_ENABLED=true`, provide a fresh `SESSION_STRING`, and use a host that stays running.

Recommended production shape:

- One always-on web service or worker process running `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- A real PostgreSQL database.
- A real Render Key Value/Redis-compatible instance. Use its internal `redis://...` connection string for `REDIS_URL`.
- `ENVIRONMENT=production`, `SCHEDULER_ENABLED=true`, `BACKGROUND_WORKERS_ENABLED=true`, and `TELEGRAM_ENABLED=true`.
- A Telegram `SESSION_STRING` generated for this deployment only. Do not reuse the same session string from a local machine and a deployed host at the same time.

Render notes:

- If Render shows `failed to configure registry cache importer ... buildcache: not found`, trigger a manual deploy with the build cache cleared. Docker documents that missing registry cache imports are cache-state failures, not application code failures.
- If Render shows `Port scan timeout reached`, confirm the service is a `web` service and the start command binds to `0.0.0.0` and `${PORT:-10000}`. This repo's Dockerfile does that.
- If logs show Redis connecting to `localhost:6379`, the `REDIS_URL` environment variable is missing or wrong. Use Render Key Value's internal connection string.

## Safe Product Boundaries

- No unsolicited outreach
- No scraping third-party groups or DMs
- No "human simulation" or anti-ban behavior
- No outbound messaging without explicit user initiation and recorded consent
- AI is limited to triage assistance and draft generation for opted-in users

## Primary API Endpoints

- `GET /health`
- `POST /api/v1/contacts`
- `GET /api/v1/contacts`
- `POST /api/v1/consents`
- `POST /api/v1/conversations`
- `POST /api/v1/messages/inbound`
- `GET /api/v1/dashboard/summary`

## Production Readiness Checklist

Before setting `ENVIRONMENT=production`, configure real deployment values and run migrations:

```bash
alembic upgrade head
```

- Set a unique `SECRET_KEY` with at least 32 characters.
- Prefer `DASHBOARD_PASSWORD_HASH` over a plain `DASHBOARD_ADMIN_PASSWORD`.
- Protect the Settings/Control page with `DASHBOARD_CONTROL_PASSWORD_HASH` or a separate strong `DASHBOARD_CONTROL_PASSWORD`.
- Point `DATABASE_URL` to the production PostgreSQL database and enable verified TLS with `DATABASE_SSL_ROOT_CERT` when your provider requires a custom CA.
- Point `REDIS_URL` to a real production Redis/Render Key Value instance. Mock Redis is for local development only.
- Set `TRUSTED_ORIGINS` and `TRUSTED_HOSTS` to the real production domains only.
- Set `TELEGRAM_ENABLED=true` only on the always-on service that should own the Telegram session.
- Keep `AUTO_CREATE_TABLES=false`; schema changes should come from Alembic migrations.
- Run `pytest -q` and `npm run test:dashboard:visual` before deployment.

## Key Docs

- [Compliant system prompt](docs/telegram_support_crm_spec.md)
- [Schema and scheduler design](docs/schema_and_jobs.md)
