"""campaign schema: immutable raw channel metrics and normalized metrics.

Revision ID: 0005_raw_normalized_metrics
Revises: 0004_connector_operations
Create Date: 2026-09-01

``raw_channel_metrics`` is append-only: provider revisions arrive as new
rows with a new retrieval/hash and an append-only trigger (reusing
``core.forbid_mutation`` from 0001) forbids UPDATE/DELETE. Duplicate
pulls are rejected by the unique source-hash key. ``normalized_metrics``
is an independent, recomputable layer: Decimal values, explicit formula
version and source raw metric IDs; unreliable conversions are stored as
``not_available`` — never imputed, never overwriting raw.

Reversible: downgrade drops exactly the objects created here.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0005_raw_normalized_metrics"
down_revision = "0004_connector_operations"
branch_labels = None
depends_on = None

_QUALITY_STATUSES = ("ok", "not_available")


def upgrade() -> None:
    op.create_table(
        "raw_channel_metrics",
        sa.Column("metric_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("external_object_id", sa.Text(), nullable=False),
        sa.Column("provider_field_name", sa.Text(), nullable=False),
        sa.Column("provider_value", JSONB, nullable=True),
        sa.Column("provider_value_type", sa.Text(), nullable=False),
        sa.Column("provider_currency", sa.Text(), nullable=True),
        sa.Column("provider_timezone", sa.Text(), nullable=False),
        sa.Column("attribution_window", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Text(), nullable=False),
        sa.Column("period_end", sa.Text(), nullable=False),
        sa.Column("provider_api_version", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_response_ref", sa.Text(), nullable=False),
        sa.Column("source_response_hash", sa.Text(), nullable=False),
        sa.Column("connector_version", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "channel",
            "external_object_id",
            "provider_field_name",
            "period_start",
            "period_end",
            "source_response_hash",
            name="uq_campaign_raw_metric_dedupe",
        ),
        sa.CheckConstraint(
            "source_response_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_campaign_raw_metric_hash",
        ),
        schema="campaign",
    )
    op.create_index(
        "ix_campaign_raw_metrics_object",
        "raw_channel_metrics",
        ["tenant_id", "channel", "external_object_id", "period_start"],
        schema="campaign",
    )
    op.execute(
        "CREATE TRIGGER raw_channel_metrics_append_only "
        "BEFORE UPDATE OR DELETE ON campaign.raw_channel_metrics "
        "FOR EACH ROW EXECUTE FUNCTION core.forbid_mutation()"
    )

    op.create_table(
        "normalized_metrics",
        sa.Column("metric_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("external_object_id", sa.Text(), nullable=False),
        sa.Column("canonical_metric", sa.Text(), nullable=False),
        sa.Column("value_decimal", sa.Numeric(38, 12), nullable=True),
        sa.Column("quality_status", sa.Text(), nullable=False),
        sa.Column("not_available_reason", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("period_start", sa.Text(), nullable=False),
        sa.Column("period_end", sa.Text(), nullable=False),
        sa.Column("formula_version", sa.Text(), nullable=False),
        sa.Column("source_raw_metric_ids", JSONB, nullable=False),
        sa.Column("freshness_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("metric_id", "calculated_at"),
        sa.CheckConstraint(
            "quality_status IN ('ok', 'not_available')",
            name="ck_campaign_normalized_quality",
        ),
        sa.CheckConstraint(
            "(quality_status = 'ok') = (value_decimal IS NOT NULL)",
            name="ck_campaign_normalized_value_presence",
        ),
        schema="campaign",
    )
    op.create_index(
        "ix_campaign_normalized_object",
        "normalized_metrics",
        ["tenant_id", "channel", "external_object_id", "canonical_metric"],
        schema="campaign",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_normalized_object",
        table_name="normalized_metrics",
        schema="campaign",
    )
    op.drop_table("normalized_metrics", schema="campaign")
    op.execute(
        "DROP TRIGGER raw_channel_metrics_append_only ON campaign.raw_channel_metrics"
    )
    op.drop_index(
        "ix_campaign_raw_metrics_object",
        table_name="raw_channel_metrics",
        schema="campaign",
    )
    op.drop_table("raw_channel_metrics", schema="campaign")
