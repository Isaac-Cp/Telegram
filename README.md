# Streamexpert Support CRM

Compliant Telegram IPTV support and CRM scaffold built for opt-in workflows only. The platform assumes users start the conversation themselves through a Telegram bot or other approved intake channel, after which support teams can triage requests, store consent, schedule follow-ups, and review AI-generated reply drafts.

## What This Scaffold Includes

- FastAPI service layout with versioned API routes
- SQLAlchemy models and Alembic migration scaffold for contacts, consents, conversations, tickets, messages, follow-up jobs, engagement profiles, activity events, and daily metrics
- Redis integration for job queue handoff
- APScheduler jobs for consent-safe reminders, engagement scoring, stale conversation handling, and daily metrics snapshots
- Documentation for the compliant system prompt and the opt-in workflow design

## Deployment & Infrastructure Recommendations

To optimize the SLIE production environment, consider the following platform-level upgrades:

- **Build Performance**: Switch to a larger build machine (e.g., Render "Plus" or Vercel Pro) to get builds up to 40% faster.
- **Concurrent Deployments**: Enable multiple simultaneous deployments to avoid waiting for queued builds during rapid iteration.
- **Version Syncing**: The platform now includes a `/health` endpoint that exposes the current `version`. Use this in your CI/CD pipeline to verify that the client and server are in sync before finalizing a rollout.
- **Custom Domains**: Use a custom domain (e.g., `api.streamexpert.com`) to provide a professional interface for your bot's callbacks and dashboard.

## Render Deployment

The repo now includes a [`render.yaml`](render.yaml) blueprint for a FastAPI web service on Render. It is set up to:

- bind to Render's injected `PORT`
- use `/ready` as the health check
- run Alembic migrations as a pre-deploy step
- keep Telegram and background workers disabled on the web tier by default
- avoid requiring Redis for a plain API deployment

If you deploy manually instead of using the blueprint, use:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Recommended Render environment variables for the web service:

- `ENVIRONMENT=production`
- `RUN_MIGRATIONS_ON_STARTUP=false` if you use the included blueprint
- `RUN_MIGRATIONS_ON_STARTUP=true` if you deploy manually without a pre-deploy migration step
- `BACKGROUND_WORKERS_ENABLED=false`
- `TELEGRAM_ENABLED=false`
- `REDIS_REQUIRED=false`

## Quick Start

1. Copy `.env.example` to `.env` and fill in the values you need.
2. Start dependencies:

```bash
docker compose up -d postgres redis
```

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

## Key Docs

- [Compliant system prompt](docs/telegram_support_crm_spec.md)
- [Schema and scheduler design](docs/schema_and_jobs.md)
