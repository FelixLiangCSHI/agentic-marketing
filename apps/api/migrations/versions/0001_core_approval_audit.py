"""core/approval/audit schemas, outbox, and append-only triggers.

Revision ID: 0001_core_approval_audit
Revises:
Create Date: 2026-08-28

Reversible: downgrade drops every object created here and nothing else.
No table locks on existing data (initial migration on empty schemas).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0001_core_approval_audit"
down_revision = None
branch_labels = None
depends_on = None

_RUN_STATUSES = (
    "CREATED",
    "PLANNING",
    "RUNNING",
    "WAITING_TOOL",
    "WAITING_APPROVAL",
    "RETRY_SCHEDULED",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "COMPENSATING",
    "COMPENSATED",
)
_RUN_EVENT_TYPES = (
    "RUN_STATUS_CHANGED",
    "TASK_STATUS_CHANGED",
    "TOOL_CALL_REQUESTED",
    "TOOL_CALL_FINISHED",
    "APPROVAL_REQUESTED",
    "APPROVAL_DECIDED",
    "CHECKPOINT_SAVED",
    "ERROR_RECORDED",
)
_TASK_STATUSES = ("PENDING", "READY", "LEASED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")
_APPROVAL_TYPES = ("content_publication", "campaign_activation", "budget_change")
_APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED", "EXPIRED", "REVOKED")
_AGENT_TYPES = ("content", "campaign")
_ENVIRONMENTS = ("local", "dev", "sit", "uat", "prd")
_DECISIONS = ("APPROVED", "REJECTED")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    op.execute("CREATE SCHEMA core")
    op.execute("CREATE SCHEMA approval")
    op.execute("CREATE SCHEMA audit")

    op.create_table(
        "runs",
        sa.Column("run_id", sa.Text(), primary_key=True),
        sa.Column(
            "parent_run_id", sa.Text(), sa.ForeignKey("core.runs.run_id"), nullable=True
        ),
        sa.Column("agent_type", sa.Text(), nullable=False),
        sa.Column("workflow_name", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("tenant", sa.Text(), nullable=False),
        sa.Column("business_unit", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in_list("status", _RUN_STATUSES), name="runs_status_check"),
        sa.CheckConstraint(_in_list("agent_type", _AGENT_TYPES), name="runs_agent_type_check"),
        sa.CheckConstraint(
            _in_list("environment", _ENVIRONMENTS), name="runs_environment_check"
        ),
        schema="core",
    )
    # status is the hot filter for schedulers/dashboards listing active runs.
    op.create_index("ix_core_runs_status", "runs", ["status"], schema="core")

    op.create_table(
        "run_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("core.runs.run_id"), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="run_events_run_id_sequence_key"),
        sa.CheckConstraint(_in_list("event_type", _RUN_EVENT_TYPES), name="run_events_type_check"),
        sa.CheckConstraint("sequence >= 0", name="run_events_sequence_check"),
        schema="core",
    )

    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("core.runs.run_id"), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_in_list("status", _TASK_STATUSES), name="tasks_status_check"),
        sa.CheckConstraint("attempt >= 0", name="tasks_attempt_check"),
        sa.CheckConstraint("max_attempts >= 1", name="tasks_max_attempts_check"),
        schema="core",
    )
    # workers poll for READY tasks per run; composite index avoids a scan.
    op.create_index("ix_core_tasks_run_id_status", "tasks", ["run_id", "status"], schema="core")

    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Text(), sa.ForeignKey("core.tasks.task_id"), primary_key=True),
        sa.Column(
            "depends_on_task_id",
            sa.Text(),
            sa.ForeignKey("core.tasks.task_id"),
            primary_key=True,
        ),
        sa.CheckConstraint(
            "task_id <> depends_on_task_id", name="task_dependencies_no_self_check"
        ),
        schema="core",
    )
    # reverse-edge lookups for the recursive reachability (cycle) check.
    op.create_index(
        "ix_core_task_dependencies_depends_on",
        "task_dependencies",
        ["depends_on_task_id"],
        schema="core",
    )

    op.create_table(
        "workflow_journal",
        sa.Column("journal_id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("core.runs.run_id"), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "sequence", name="workflow_journal_run_id_sequence_key"),
        schema="core",
    )

    op.create_table(
        "outbox",
        sa.Column("outbox_id", sa.Text(), primary_key=True),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        schema="core",
    )
    # partial index: the dispatcher only ever scans undelivered messages.
    op.create_index(
        "ix_core_outbox_pending",
        "outbox",
        ["created_at"],
        schema="core",
        postgresql_where=sa.text("dispatched_at IS NULL"),
    )

    op.create_table(
        "requests",
        sa.Column("approval_id", sa.Text(), primary_key=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("core.runs.run_id"), nullable=False),
        sa.Column("approval_type", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("input_artifact_hash", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(_in_list("approval_type", _APPROVAL_TYPES), name="requests_type_check"),
        sa.CheckConstraint(_in_list("status", _APPROVAL_STATUSES), name="requests_status_check"),
        schema="approval",
    )
    op.create_index("ix_approval_requests_run_id", "requests", ["run_id"], schema="approval")

    op.create_table(
        "decisions",
        sa.Column("decision_id", sa.Text(), primary_key=True),
        sa.Column(
            "approval_id",
            sa.Text(),
            sa.ForeignKey("approval.requests.approval_id"),
            nullable=False,
        ),
        sa.Column("approver_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("approval_id", name="decisions_approval_id_key"),
        sa.CheckConstraint(_in_list("decision", _DECISIONS), name="decisions_decision_check"),
        schema="approval",
    )

    op.create_table(
        "tokens",
        sa.Column("token_id", sa.Text(), primary_key=True),
        sa.Column(
            "approval_id",
            sa.Text(),
            sa.ForeignKey("approval.requests.approval_id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by", sa.Text(), nullable=True),
        sa.UniqueConstraint("token_hash", name="tokens_token_hash_key"),
        sa.UniqueConstraint("approval_id", name="tokens_approval_id_key"),
        schema="approval",
    )

    op.create_table(
        "events",
        sa.Column("audit_id", sa.Text(), primary_key=True),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        schema="audit",
    )
    op.create_index("ix_audit_events_run_id", "events", ["run_id"], schema="audit")
    op.create_index(
        "ix_audit_events_resource", "events", ["resource_type", "resource_id"], schema="audit"
    )

    # run_events and audit.events are append-only: any UPDATE or DELETE is
    # rejected at the database level, regardless of the application role.
    op.execute(
        """
        CREATE FUNCTION core.forbid_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '%.% is append-only; % is forbidden',
                TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER run_events_append_only BEFORE UPDATE OR DELETE ON core.run_events "
        "FOR EACH ROW EXECUTE FUNCTION core.forbid_mutation()"
    )
    op.execute(
        "CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit.events "
        "FOR EACH ROW EXECUTE FUNCTION core.forbid_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_events_append_only ON audit.events")
    op.execute("DROP TRIGGER run_events_append_only ON core.run_events")
    op.execute("DROP FUNCTION core.forbid_mutation()")
    op.drop_table("events", schema="audit")
    op.drop_table("tokens", schema="approval")
    op.drop_table("decisions", schema="approval")
    op.drop_table("requests", schema="approval")
    op.drop_table("outbox", schema="core")
    op.drop_table("workflow_journal", schema="core")
    op.drop_table("task_dependencies", schema="core")
    op.drop_table("tasks", schema="core")
    op.drop_table("run_events", schema="core")
    op.drop_table("runs", schema="core")
    op.execute("DROP SCHEMA audit")
    op.execute("DROP SCHEMA approval")
    op.execute("DROP SCHEMA core")
