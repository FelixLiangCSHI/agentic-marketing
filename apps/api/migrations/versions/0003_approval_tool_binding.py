"""Persist approval token tool and agent binding.

Revision ID: 0003_approval_tool_binding
Revises: 0002_approval_binding
Create Date: 2026-08-28

Stores the host-side L3 permission binding fields used when consuming approval
tokens so a token minted for one tool/agent pair cannot authorize another.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_approval_tool_binding"
down_revision = "0002_approval_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("tool_name", sa.Text(), nullable=False, server_default=""),
        schema="approval",
    )
    op.add_column(
        "requests",
        sa.Column("agent_type", sa.Text(), nullable=False, server_default=""),
        schema="approval",
    )


def downgrade() -> None:
    op.drop_column("requests", "agent_type", schema="approval")
    op.drop_column("requests", "tool_name", schema="approval")
