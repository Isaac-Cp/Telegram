"""initial schema"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


contact_status = sa.Enum("NEW", "ACTIVE", "CLOSED", name="contact_status")
consent_channel = sa.Enum("TELEGRAM", "EMAIL", "PHONE", name="consent_channel")
consent_scope = sa.Enum(
    "SUPPORT_UPDATES",
    "DEMO_FOLLOW_UPS",
    "PRODUCT_UPDATES",
    "RESELLER_PROGRAM",
    name="consent_scope",
)
lifecycle_stage = sa.Enum(
    "NEW",
    "QUALIFIED",
    "SUPPORT_ACTIVE",
    "DEMO_SCHEDULED",
    "CUSTOMER",
    "RESELLER_INTEREST",
    "CLOSED",
    name="lifecycle_stage",
)
conversation_status = sa.Enum("OPEN", "PENDING", "CLOSED", name="conversation_status")
message_direction = sa.Enum("INBOUND", "OUTBOUND", name="message_direction")
ticket_status = sa.Enum("OPEN", "PENDING", "RESOLVED", "CLOSED", name="ticket_status")
ticket_priority = sa.Enum("LOW", "MEDIUM", "HIGH", name="ticket_priority")
ticket_category = sa.Enum(
    "TECH_SUPPORT",
    "BILLING",
    "DEMO_REQUEST",
    "RESELLER_INQUIRY",
    "GENERAL",
    name="ticket_category",
)
follow_up_job_type = sa.Enum(
    "SUPPORT_CHECKIN",
    "DEMO_REMINDER",
    "RESELLER_FOLLOW_UP",
    "CONVERSATION_CLOSURE",
    name="follow_up_job_type",
)
follow_up_job_status = sa.Enum(
    "QUEUED",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    name="follow_up_job_status",
)
event_type = sa.Enum(
    "USER_STARTED_CHAT",
    "CONSENT_GRANTED",
    "CONSENT_REVOKED",
    "MESSAGE_RECEIVED",
    "MESSAGE_SENT",
    "TICKET_OPENED",
    "TICKET_RESOLVED",
    "FOLLOW_UP_QUEUED",
    "FOLLOW_UP_CANCELLED",
    "CONVERSATION_CLOSED",
    name="event_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    contact_status.create(bind, checkfirst=True)
    consent_channel.create(bind, checkfirst=True)
    consent_scope.create(bind, checkfirst=True)
    lifecycle_stage.create(bind, checkfirst=True)
    conversation_status.create(bind, checkfirst=True)
    message_direction.create(bind, checkfirst=True)
    ticket_status.create(bind, checkfirst=True)
    ticket_priority.create(bind, checkfirst=True)
    ticket_category.create(bind, checkfirst=True)
    follow_up_job_type.create(bind, checkfirst=True)
    follow_up_job_status.create(bind, checkfirst=True)
    event_type.create(bind, checkfirst=True)

    op.create_table(
        "contacts",
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", contact_status, nullable=False),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_contacts_telegram_user_id")),
    )
    op.create_index(op.f("ix_contacts_telegram_user_id"), "contacts", ["telegram_user_id"], unique=False)

    op.create_table(
        "lead_profiles",
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("lifecycle_stage", lifecycle_stage, nullable=False),
        sa.Column("engagement_score", sa.Integer(), nullable=False),
        sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_lead_profiles_contact_id_contacts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_profiles")),
        sa.UniqueConstraint("contact_id", name=op.f("uq_lead_profiles_contact_id")),
    )
    op.create_index(op.f("ix_lead_profiles_contact_id"), "lead_profiles", ["contact_id"], unique=True)

    op.create_table(
        "conversations",
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("status", conversation_status, nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("assigned_agent", sa.String(length=255), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_conversations_contact_id_contacts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(op.f("ix_conversations_contact_id"), "conversations", ["contact_id"], unique=False)

    op.create_table(
        "consents",
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("channel", consent_channel, nullable=False),
        sa.Column("scope", consent_scope, nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("proof_text", sa.String(length=500), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_consents_contact_id_contacts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consents")),
    )
    op.create_index(op.f("ix_consents_contact_id"), "consents", ["contact_id"], unique=False)

    op.create_table(
        "activity_events",
        sa.Column("contact_id", sa.String(), nullable=True),
        sa.Column("event_type", event_type, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_activity_events_contact_id_contacts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_events")),
    )
    op.create_index(op.f("ix_activity_events_contact_id"), "activity_events", ["contact_id"], unique=False)
    op.create_index(op.f("ix_activity_events_occurred_at"), "activity_events", ["occurred_at"], unique=False)

    op.create_table(
        "tickets",
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_tickets_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_tickets_conversation_id_conversations"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
    )
    op.create_index(op.f("ix_tickets_contact_id"), "tickets", ["contact_id"], unique=False)
    op.create_index(op.f("ix_tickets_conversation_id"), "tickets", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_tickets_next_follow_up_at"), "tickets", ["next_follow_up_at"], unique=False)

    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ai_draft", sa.Boolean(), nullable=False),
        sa.Column("human_approved", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_messages_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], name=op.f("fk_messages_conversation_id_conversations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(op.f("ix_messages_contact_id"), "messages", ["contact_id"], unique=False)
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)

    op.create_table(
        "follow_up_jobs",
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("ticket_id", sa.String(), nullable=True),
        sa.Column("job_type", follow_up_job_type, nullable=False),
        sa.Column("status", follow_up_job_status, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_follow_up_jobs_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name=op.f("fk_follow_up_jobs_ticket_id_tickets"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_follow_up_jobs")),
    )
    op.create_index(op.f("ix_follow_up_jobs_contact_id"), "follow_up_jobs", ["contact_id"], unique=False)
    op.create_index(op.f("ix_follow_up_jobs_run_at"), "follow_up_jobs", ["run_at"], unique=False)
    op.create_index(op.f("ix_follow_up_jobs_status"), "follow_up_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_follow_up_jobs_ticket_id"), "follow_up_jobs", ["ticket_id"], unique=False)

    op.create_table(
        "metrics_snapshots",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("contacts_total", sa.Integer(), nullable=False),
        sa.Column("open_conversations", sa.Integer(), nullable=False),
        sa.Column("open_tickets", sa.Integer(), nullable=False),
        sa.Column("inbound_messages", sa.Integer(), nullable=False),
        sa.Column("outbound_messages", sa.Integer(), nullable=False),
        sa.Column("follow_ups_due", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metrics_snapshots")),
        sa.UniqueConstraint("day", name=op.f("uq_metrics_snapshots_day")),
    )
    op.create_index(op.f("ix_metrics_snapshots_day"), "metrics_snapshots", ["day"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_metrics_snapshots_day"), table_name="metrics_snapshots")
    op.drop_table("metrics_snapshots")

    op.drop_index(op.f("ix_follow_up_jobs_ticket_id"), table_name="follow_up_jobs")
    op.drop_index(op.f("ix_follow_up_jobs_status"), table_name="follow_up_jobs")
    op.drop_index(op.f("ix_follow_up_jobs_run_at"), table_name="follow_up_jobs")
    op.drop_index(op.f("ix_follow_up_jobs_contact_id"), table_name="follow_up_jobs")
    op.drop_table("follow_up_jobs")

    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_contact_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_tickets_next_follow_up_at"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_conversation_id"), table_name="tickets")
    op.drop_index(op.f("ix_tickets_contact_id"), table_name="tickets")
    op.drop_table("tickets")

    op.drop_index(op.f("ix_activity_events_occurred_at"), table_name="activity_events")
    op.drop_index(op.f("ix_activity_events_contact_id"), table_name="activity_events")
    op.drop_table("activity_events")

    op.drop_index(op.f("ix_consents_contact_id"), table_name="consents")
    op.drop_table("consents")

    op.drop_index(op.f("ix_conversations_contact_id"), table_name="conversations")
    op.drop_table("conversations")

    op.drop_index(op.f("ix_lead_profiles_contact_id"), table_name="lead_profiles")
    op.drop_table("lead_profiles")

    op.drop_index(op.f("ix_contacts_telegram_user_id"), table_name="contacts")
    op.drop_table("contacts")

    bind = op.get_bind()
    event_type.drop(bind, checkfirst=True)
    follow_up_job_status.drop(bind, checkfirst=True)
    follow_up_job_type.drop(bind, checkfirst=True)
    ticket_category.drop(bind, checkfirst=True)
    ticket_priority.drop(bind, checkfirst=True)
    ticket_status.drop(bind, checkfirst=True)
    message_direction.drop(bind, checkfirst=True)
    conversation_status.drop(bind, checkfirst=True)
    lifecycle_stage.drop(bind, checkfirst=True)
    consent_scope.drop(bind, checkfirst=True)
    consent_channel.drop(bind, checkfirst=True)
    contact_status.drop(bind, checkfirst=True)

