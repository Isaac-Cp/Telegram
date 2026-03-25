# Schema And Scheduler Design

## Database Schema

### `contacts`

- Stores the person record for an opted-in Telegram user or imported CRM contact.
- Key fields: `telegram_user_id`, `username`, `status`, `source`, `last_inbound_at`, `last_outbound_at`

### `consents`

- Stores explicit consent history by channel and scope.
- Active consent means `granted_at` is set and `revoked_at` is null.
- Follow-up jobs must check this table before sending anything.

### `lead_profiles`

- Safe lifecycle and engagement layer for contacts who have already opted in.
- Contains `lifecycle_stage`, `engagement_score`, and `last_scored_at`.

### `conversations`

- Message thread per contact and topic.
- Holds current `status`, `channel`, and assignment fields.

### `messages`

- Timeline of inbound and outbound communication.
- Tracks draft provenance with `ai_draft` and `human_approved`.

### `tickets`

- Support or commercial case created from a conversation.
- Holds `category`, `priority`, `status`, SLA timestamps, and `next_follow_up_at`.

### `follow_up_jobs`

- Queueable reminders and nurture tasks for active-consent contacts.
- Status lifecycle: `QUEUED -> PROCESSING -> COMPLETED | FAILED | CANCELLED`

### `activity_events`

- Audit and analytics event log.
- Useful for daily metrics, dashboards, and compliance review.

### `metrics_snapshots`

- Daily aggregate table for dashboard charts.
- Stores counts for inbound messages, outbound messages, open tickets, and due follow-ups.

## Scheduler Jobs

### `queue_due_follow_ups`

- Runs every 5 minutes.
- Finds open tickets with `next_follow_up_at <= now`.
- Verifies active consent.
- Creates `follow_up_jobs` rows and pushes IDs to Redis.

### `cancel_revoked_follow_ups`

- Runs every 5 minutes.
- Cancels queued follow-ups for contacts whose consent was revoked.
- Ensures no outbound reminder can be sent after revocation.

### `refresh_engagement_scores`

- Runs every 15 minutes.
- Recalculates `lead_profiles.engagement_score` from recent inbound activity, ticket state, and consent freshness.
- Updates lifecycle stage when the user reaches milestones such as `DEMO_SCHEDULED` or `RESELLER_INTEREST`.

### `close_stale_conversations`

- Runs hourly.
- Closes conversations with no messages for a defined inactivity window and no open tickets.
- Creates an audit event so staff can review automated closure behavior.

### `snapshot_daily_metrics`

- Runs once daily.
- Writes a daily aggregate to `metrics_snapshots` for dashboards and historical reporting.

## Recommended Opt-In Flow

1. User starts the Telegram bot or submits an approved contact form.
2. Intake endpoint upserts the contact and creates a conversation.
3. Consent is recorded for the relevant follow-up scopes.
4. A ticket is created when the issue requires structured handling.
5. AI can classify urgency and draft a response, but staff can review before sending.
6. Scheduler jobs create reminders only when consent remains active.

