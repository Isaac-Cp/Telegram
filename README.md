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
