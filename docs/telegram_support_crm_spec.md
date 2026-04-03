# COMPLIANT BUILD SPEC

## Telegram IPTV Support + CRM Platform

```text
PROJECT NAME:
Streamexpert Support CRM (SSCRM)

OBJECTIVE:
Build a compliant Telegram support and CRM platform for Streamexpert that helps opted-in users troubleshoot IPTV issues, request demos, ask billing questions, and move through a transparent sales or support lifecycle with consent, logging, and human oversight.

The system must only interact with users who initiate contact through approved channels or who have given explicit consent for follow-up.
```

## 1 Core System Overview

The system must contain 8 compliant modules.

```text
1 Consent + Channel Enrollment Engine
2 Inbound Support Intake Engine
3 AI Triage + Draft Assistant
4 CRM + Lifecycle Engine
5 Conversation Memory Engine
6 Follow-Up Scheduler
7 Compliance Guardrails Engine
8 Analytics + Dashboard
```

## 2 Technology Stack

Use the following stack:

```text
Python 3.11+
FastAPI
PostgreSQL
Redis
SQLAlchemy + Alembic
APScheduler
OpenAI API
Telegram Bot API or approved webhook-based intake
```

Optional but recommended:

```text
Docker
Role-based admin UI
Audit logging
```

## 3 Telegram Setup

Use a Telegram bot or another approved Telegram integration that only receives inbound messages from users who initiate contact.

Requirements:

```text
bot token
webhook or polling support
message update verification
conversation logging
```

The system must not simulate a human user, bypass platform limits, or message people who did not ask to be contacted.

## 4 Consent + Enrollment Engine

Track every opt-in event and its scope.

Consent scopes:

```text
SUPPORT_UPDATES
DEMO_FOLLOW_UPS
PRODUCT_UPDATES
RESELLER_PROGRAM
```

Store:

```text
contact_id
channel
scope
granted_at
revoked_at
source
proof_text
```

Rules:

```text
No outbound follow-up without active consent for that scope
Revocation must immediately suppress queued follow-ups
```

## 5 Inbound Support Intake Engine

Capture only user-initiated inbound requests.

Store:

```text
external_message_id
telegram_user_id
username
message_text
received_at
topic
```

Support categories:

```text
TECH_SUPPORT
BILLING
DEMO_REQUEST
RESELLER_INQUIRY
GENERAL
```

## 6 AI Triage + Draft Assistant

Use an LLM to classify inbound intent and urgency from inbound messages, then propose reply drafts for review.

Prompt:

```text
Classify the user's support intent and urgency from this inbound message.

Return JSON:
{
  "category": "TECH_SUPPORT | BILLING | DEMO_REQUEST | RESELLER_INQUIRY | GENERAL",
  "priority": "LOW | MEDIUM | HIGH",
  "summary": "brief summary",
  "needs_human_review": true
}
```

AI may also draft replies, but each draft must remain reviewable and attributable.

## 7 CRM + Lifecycle Engine

Track contact lifecycle for opted-in users.

Lifecycle stages:

```text
NEW
QUALIFIED
SUPPORT_ACTIVE
DEMO_SCHEDULED
CUSTOMER
RESELLER_INTEREST
CLOSED
```

The system must store:

```text
contact record
consent status
conversation history
tickets
engagement score
follow-up tasks
```

## 8 Conversation Memory Engine

Store all inbound and outbound messages in a single timeline per conversation.

Track:

```text
direction
body
sent_at
ai_draft
human_approved
metadata
```

## 9 Follow-Up Scheduler

Only create reminders for contacts with active consent.

Example jobs:

```text
support check-in after unresolved issue
demo reminder after user requested a demo
reseller follow-up after pricing request
conversation closure after inactivity
```

## 10 Compliance Guardrails Engine

Requirements:

```text
block outbound jobs when consent is missing or revoked
cancel queued jobs after revocation
record audit events for every consent change and outbound action
store human approval status for AI-generated drafts
```

## 11 Analytics Dashboard

Show:

```text
opt-ins by source
open conversations
open tickets
reply SLA compliance
follow-ups due
conversion by lifecycle stage
```

Charts:

```text
daily inbound messages
ticket resolution trend
consent growth
lifecycle funnel
```

## 12 Automated Workflow

Scheduler tasks:

```text
ingest inbound webhook events
queue_due_follow_ups()
cancel_revoked_follow_ups()
refresh_engagement_scores()
close_stale_conversations()
snapshot_daily_metrics()
```

Run every 2-15 minutes depending on load, with daily snapshot jobs once per day.

## 13 Final Development Requirements

The code must be:

```text
modular
auditable
consent-aware
production-ready
```

Include:

```text
config file
logging
error handling
database migrations
clear module structure
documentation
```
