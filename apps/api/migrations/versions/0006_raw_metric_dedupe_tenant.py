"""raw metric dedupe key includes tenant and account.

Revision ID: 0006_raw_metric_dedupe_tenant
Revises: 0005_raw_normalized_metrics
Create Date: 2026-09-01

The raw metric dedupe key must be scoped to the owning tenant and
account: without them, a row from one tenant/account could shadow an
identical-looking pull for another. This matches the in-process
``RawMetricRecord.dedupe_key()``.

Reversible: downgrade restores the previous constraint definition.
"""

from __future__ import annotations

from alembic import op

revision = "0006_raw_metric_dedupe_tenant"
down_revision = "0005_raw_normalized_metrics"
branch_labels = None
depends_on = None

_OLD_COLUMNS = (
    "channel",
    "external_object_id",
    "provider_field_name",
    "period_start",
    "period_end",
    "source_response_hash",
)
_NEW_COLUMNS = ("tenant_id", "account_id") + _OLD_COLUMNS


def upgrade() -> None:
    op.drop_constraint(
        "uq_campaign_raw_metric_dedupe",
        "raw_channel_metrics",
        schema="campaign",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_campaign_raw_metric_dedupe",
        "raw_channel_metrics",
        list(_NEW_COLUMNS),
        schema="campaign",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_campaign_raw_metric_dedupe",
        "raw_channel_metrics",
        schema="campaign",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_campaign_raw_metric_dedupe",
        "raw_channel_metrics",
        list(_OLD_COLUMNS),
        schema="campaign",
    )
