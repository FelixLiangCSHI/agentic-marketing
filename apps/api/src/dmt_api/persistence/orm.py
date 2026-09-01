"""SQLAlchemy table definitions mirrored by the Alembic migrations.

The Alembic migration under ``migrations/versions`` is the authoritative DDL
(including append-only triggers). This metadata exists for typed queries in
repositories and for autogenerate comparisons — never for ``create_all`` in
production code paths.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

RUN_STATUSES = (
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
RUN_EVENT_TYPES = (
    "RUN_STATUS_CHANGED",
    "TASK_STATUS_CHANGED",
    "TOOL_CALL_REQUESTED",
    "TOOL_CALL_FINISHED",
    "APPROVAL_REQUESTED",
    "APPROVAL_DECIDED",
    "CHECKPOINT_SAVED",
    "ERROR_RECORDED",
)
TASK_STATUSES = ("PENDING", "READY", "LEASED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED")
APPROVAL_TYPES = ("content_publication", "campaign_activation", "budget_change")
APPROVAL_STATUSES = ("PENDING", "APPROVED", "REJECTED", "EXPIRED", "REVOKED")
AGENT_TYPES = ("content", "campaign")
ENVIRONMENTS = ("local", "dev", "sit", "uat", "prd")
DECISIONS = ("APPROVED", "REJECTED")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(_in_list("status", RUN_STATUSES), name="runs_status_check"),
        CheckConstraint(_in_list("agent_type", AGENT_TYPES), name="runs_agent_type_check"),
        CheckConstraint(_in_list("environment", ENVIRONMENTS), name="runs_environment_check"),
        Index("ix_core_runs_status", "status"),
        {"schema": "core"},
    )

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    parent_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("core.runs.run_id"), nullable=True
    )
    agent_type: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_name: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    tenant: Mapped[str] = mapped_column(Text, nullable=False)
    business_unit: Mapped[str] = mapped_column(Text, nullable=False)
    requester_id: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunEventRow(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="run_events_run_id_sequence_key"),
        CheckConstraint(_in_list("event_type", RUN_EVENT_TYPES), name="run_events_type_check"),
        CheckConstraint("sequence >= 0", name="run_events_sequence_check"),
        {"schema": "core"},
    )

    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("core.runs.run_id"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(_in_list("status", TASK_STATUSES), name="tasks_status_check"),
        CheckConstraint("attempt >= 0", name="tasks_attempt_check"),
        CheckConstraint("max_attempts >= 1", name="tasks_max_attempts_check"),
        Index("ix_core_tasks_run_id_status", "run_id", "status"),
        {"schema": "core"},
    )

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("core.runs.run_id"), nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaskDependencyRow(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint("task_id <> depends_on_task_id", name="task_dependencies_no_self_check"),
        Index("ix_core_task_dependencies_depends_on", "depends_on_task_id"),
        {"schema": "core"},
    )

    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("core.tasks.task_id"), primary_key=True
    )
    depends_on_task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("core.tasks.task_id"), primary_key=True
    )


class JournalRow(Base):
    __tablename__ = "workflow_journal"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="workflow_journal_run_id_sequence_key"),
        {"schema": "core"},
    )

    journal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("core.runs.run_id"), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    node_name: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxRow(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index(
            "ix_core_outbox_pending",
            "created_at",
            postgresql_where="dispatched_at IS NULL",
        ),
        {"schema": "core"},
    )

    outbox_id: Mapped[str] = mapped_column(Text, primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ApprovalRequestRow(Base):
    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(_in_list("approval_type", APPROVAL_TYPES), name="requests_type_check"),
        CheckConstraint(_in_list("status", APPROVAL_STATUSES), name="requests_status_check"),
        Index("ix_approval_requests_run_id", "run_id"),
        {"schema": "approval"},
    )

    approval_id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("core.runs.run_id"), nullable=False)
    approval_type: Mapped[str] = mapped_column(Text, nullable=False)
    requester_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    input_artifact_hash: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    binding: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    binding_hash: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    agent_type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ApprovalDecisionRow(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        UniqueConstraint("approval_id", name="decisions_approval_id_key"),
        CheckConstraint(_in_list("decision", DECISIONS), name="decisions_decision_check"),
        {"schema": "approval"},
    )

    decision_id: Mapped[str] = mapped_column(Text, primary_key=True)
    approval_id: Mapped[str] = mapped_column(
        Text, ForeignKey("approval.requests.approval_id"), nullable=False
    )
    approver_id: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApprovalTokenRow(Base):
    __tablename__ = "tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="tokens_token_hash_key"),
        UniqueConstraint("approval_id", name="tokens_approval_id_key"),
        {"schema": "approval"},
    )

    token_id: Mapped[str] = mapped_column(Text, primary_key=True)
    approval_id: Mapped[str] = mapped_column(
        Text, ForeignKey("approval.requests.approval_id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_audit_events_run_id", "run_id"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        {"schema": "audit"},
    )

    audit_id: Mapped[str] = mapped_column(Text, primary_key=True)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


OPERATION_STATUSES = (
    "INTENT",
    "SUCCEEDED",
    "UNKNOWN",
    "RECONCILED",
    "WAITING_RECONCILIATION",
    "FAILED",
    "COMPENSATION_PENDING",
)
COMPENSATION_STATUSES = ("PENDING_APPROVAL", "APPROVED", "EXECUTED", "REJECTED")


class ConnectorOperationRow(Base):
    __tablename__ = "connector_operations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "channel",
            "account_id",
            "idempotency_key",
            name="uq_campaign_operation_key",
        ),
        CheckConstraint(
            _in_list("status", OPERATION_STATUSES),
            name="ck_campaign_operation_status",
        ),
        CheckConstraint(
            "input_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_campaign_operation_input_hash",
        ),
        {"schema": "campaign"},
    )

    operation_pk: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    approval_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    external_object_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompensationTaskRow(Base):
    __tablename__ = "compensation_tasks"
    __table_args__ = (
        CheckConstraint(
            _in_list("status", COMPENSATION_STATUSES),
            name="ck_campaign_compensation_status",
        ),
        {"schema": "campaign"},
    )

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_object_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="PENDING_APPROVAL"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


METRIC_QUALITY_STATUSES = ("ok", "not_available")


class RawChannelMetricRow(Base):
    __tablename__ = "raw_channel_metrics"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "account_id",
            "channel",
            "external_object_id",
            "provider_field_name",
            "period_start",
            "period_end",
            "source_response_hash",
            name="uq_campaign_raw_metric_dedupe",
        ),
        CheckConstraint(
            "source_response_hash ~ '^sha256:[0-9a-f]{64}$'",
            name="ck_campaign_raw_metric_hash",
        ),
        Index(
            "ix_campaign_raw_metrics_object",
            "tenant_id",
            "channel",
            "external_object_id",
            "period_start",
        ),
        {"schema": "campaign"},
    )

    metric_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_object_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_field_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    provider_value_type: Mapped[str] = mapped_column(Text, nullable=False)
    provider_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_timezone: Mapped[str] = mapped_column(Text, nullable=False)
    attribution_window: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[str] = mapped_column(Text, nullable=False)
    period_end: Mapped[str] = mapped_column(Text, nullable=False)
    provider_api_version: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_response_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_response_hash: Mapped[str] = mapped_column(Text, nullable=False)
    connector_version: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)


class NormalizedMetricRow(Base):
    __tablename__ = "normalized_metrics"
    __table_args__ = (
        CheckConstraint(
            "quality_status IN ('ok', 'not_available')",
            name="ck_campaign_normalized_quality",
        ),
        CheckConstraint(
            "(quality_status = 'ok') = (value_decimal IS NOT NULL)",
            name="ck_campaign_normalized_value_presence",
        ),
        Index(
            "ix_campaign_normalized_object",
            "tenant_id",
            "channel",
            "external_object_id",
            "canonical_metric",
        ),
        {"schema": "campaign"},
    )

    metric_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    external_object_id: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_metric: Mapped[str] = mapped_column(Text, nullable=False)
    value_decimal: Mapped[Decimal | None] = mapped_column(Numeric(38, 12), nullable=True)
    quality_status: Mapped[str] = mapped_column(Text, nullable=False)
    not_available_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_start: Mapped[str] = mapped_column(Text, nullable=False)
    period_end: Mapped[str] = mapped_column(Text, nullable=False)
    formula_version: Mapped[str] = mapped_column(Text, nullable=False)
    source_raw_metric_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    freshness_retrieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
