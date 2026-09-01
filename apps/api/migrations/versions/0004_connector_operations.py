"""campaign schema: connector operations ledger and compensation tasks.

Revision ID: 0004_connector_operations
Revises: 0003_approval_tool_binding
Create Date: 2026-09-01

One logical external write per ``(tenant_id, channel, account_id,
idempotency_key)``; the bound ``input_hash`` is stored on the row and a
conflicting hash for the same key must be rejected by the application (the
unique constraint guarantees a single row to compare against). Statuses
mirror ``campaign_activation.models.OperationStatus``. Compensation tasks
are pending-approval runbook entries only — no automatic L4 execution.

Reversible: downgrade drops exactly the objects created here.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0004_connector_operations"
down_revision = "0003_approval_tool_binding"
branch_labels = None
depends_on = None

_OPERATION_STATUSES = (
    "INTENT",
    "SUCCEEDED",
    "UNKNOWN",
    "RECONCILED",
    "WAITING_RECONCILIATION",
    "FAILED",
    "COMPENSATION_PENDING",
)

_COMPENSATION_STATUSES = ("PENDING_APPROVAL", "APPROVED", "EXECUTED", "REJECTED")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    op.execute("CREATE SCHEMA campaign")

    op.create_table(
        "connector_operations",
        sa.Column("operation_pk", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("approval_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("external_object_id", sa.Text(), nullable=True),
        sa.Column("operation_id", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "channel",
            "account_id",
            "idempotency_key",
            name="uq_campaign_operation_key",
        ),
        sa.CheckConstraint(
            _in_list("status", _OPERATION_STATUSES),
            name="ck_campaign_operation_status",
        ),
        sa.CheckConstraint(
            "input_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_campaign_operation_input_hash",
        ),
        schema="campaign",
    )
    op.create_index(
        "ix_campaign_operations_unresolved",
        "connector_operations",
        ["updated_at"],
        schema="campaign",
        postgresql_where="status IN ('UNKNOWN', 'WAITING_RECONCILIATION')",
    )

    op.create_table(
        "compensation_tasks",
        sa.Column("task_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("created_object_ids", JSONB, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="PENDING_APPROVAL"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("status", _COMPENSATION_STATUSES),
            name="ck_campaign_compensation_status",
        ),
        schema="campaign",
    )


def downgrade() -> None:
    op.drop_table("compensation_tasks", schema="campaign")
    op.drop_index(
        "ix_campaign_operations_unresolved",
        table_name="connector_operations",
        schema="campaign",
    )
    op.drop_table("connector_operations", schema="campaign")
    op.execute("DROP SCHEMA campaign")
