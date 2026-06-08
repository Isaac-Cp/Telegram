"""dashboard settings and summary indexes"""

from alembic import op
import sqlalchemy as sa


revision = "2d9f5f0c7c42"
down_revision = "9813b7f838ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_settings")),
        sa.UniqueConstraint("key", name=op.f("uq_dashboard_settings_key")),
    )
    op.create_index(op.f("ix_dashboard_settings_key"), "dashboard_settings", ["key"], unique=True)

    op.create_index(
        "ix_dashboard_messages_direction_sent_at",
        "messages",
        ["direction", "sent_at"],
        unique=False,
    )
    op.create_index("ix_dashboard_leads_created_at", "leads", ["created_at"], unique=False)
    op.create_index(
        "ix_dashboard_leads_dm_stage",
        "leads",
        ["dm_sent", "conversion_stage"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_leads_persona_stage",
        "leads",
        ["persona_id", "conversion_stage"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_groups_joined_authority",
        "groups",
        ["joined", "authority_score"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_tickets_status_priority",
        "tickets",
        ["status", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_consents_scope_revoked",
        "consents",
        ["scope", "revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_lead_profiles_lifecycle",
        "lead_profiles",
        ["lifecycle_stage"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_unified_conversations_timestamp",
        "unified_conversations",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_conversation_summary_problem_type",
        "conversation_summary",
        ["problem_type"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_lead_value_scores_tier_score",
        "lead_value_scores",
        ["ltv_tier", "ltv_score"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_conversion_predictions_tier",
        "conversion_predictions",
        ["conversion_tier"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_competitor_insights_weakness",
        "competitor_insights",
        ["weakness_score"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_influence_profiles_level",
        "influence_profiles",
        ["influence_level"],
        unique=False,
    )
    op.create_index(
        "ix_dashboard_message_analysis_problem_type",
        "message_analysis",
        ["problem_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_message_analysis_problem_type", table_name="message_analysis")
    op.drop_index("ix_dashboard_influence_profiles_level", table_name="influence_profiles")
    op.drop_index("ix_dashboard_competitor_insights_weakness", table_name="competitor_insights")
    op.drop_index("ix_dashboard_conversion_predictions_tier", table_name="conversion_predictions")
    op.drop_index("ix_dashboard_lead_value_scores_tier_score", table_name="lead_value_scores")
    op.drop_index("ix_dashboard_conversation_summary_problem_type", table_name="conversation_summary")
    op.drop_index("ix_dashboard_unified_conversations_timestamp", table_name="unified_conversations")
    op.drop_index("ix_dashboard_lead_profiles_lifecycle", table_name="lead_profiles")
    op.drop_index("ix_dashboard_consents_scope_revoked", table_name="consents")
    op.drop_index("ix_dashboard_tickets_status_priority", table_name="tickets")
    op.drop_index("ix_dashboard_groups_joined_authority", table_name="groups")
    op.drop_index("ix_dashboard_leads_persona_stage", table_name="leads")
    op.drop_index("ix_dashboard_leads_dm_stage", table_name="leads")
    op.drop_index("ix_dashboard_leads_created_at", table_name="leads")
    op.drop_index("ix_dashboard_messages_direction_sent_at", table_name="messages")
    op.drop_index(op.f("ix_dashboard_settings_key"), table_name="dashboard_settings")
    op.drop_table("dashboard_settings")
