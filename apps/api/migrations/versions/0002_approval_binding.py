"""Approval binding and token revocation columns.

Revision ID: 0002_approval_binding
Revises: 0001_core_approval_audit
Create Date: 2026-08-28

Adds the immutable approval binding (artifact hash plus policy/prompt/skill/
workflow versions, scope, account, budget and time window) to approval
requests, and revocation metadata to approval tokens so a token minted for
one input can be invalidated when the input changes.

Reversible: downgrade drops exactly the four added columns. ``ADD COLUMN``
with a constant default and nullable columns take only a brief metadata
lock on PostgreSQL 16.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002_approval_binding"
down_revision = "0001_core_approval_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column(
            "binding",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="approval",
    )
    op.add_column(
        "requests",
        sa.Column("binding_hash", sa.Text(), nullable=False, server_default=""),
        schema="approval",
    )
    op.add_column(
        "tokens",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        schema="approval",
    )
    op.add_column(
        "tokens",
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        schema="approval",
    )


def downgrade() -> None:
    op.drop_column("tokens", "revoked_reason", schema="approval")
    op.drop_column("tokens", "revoked_at", schema="approval")
    op.drop_column("requests", "binding_hash", schema="approval")
    op.drop_column("requests", "binding", schema="approval")
