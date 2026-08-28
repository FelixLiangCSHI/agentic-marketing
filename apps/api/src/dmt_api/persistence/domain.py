"""Frozen domain objects returned by repositories.

Statuses and field names mirror the v1 contracts in
``packages/domain-contracts`` (see ``dmt_api.contracts``). Repositories map
database rows to these objects; SQLAlchemy types never leak to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Run:
    run_id: str
    parent_run_id: str | None
    agent_type: str
    workflow_name: str
    workflow_version: str
    tenant: str
    business_unit: str
    requester_id: str
    environment: str
    status: str
    version: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunEvent:
    event_id: str
    run_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    run_id: str
    task_type: str
    status: str
    attempt: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    version: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class JournalEntry:
    journal_id: str
    run_id: str
    sequence: int
    node_name: str
    payload: dict[str, Any]
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    approval_id: str
    run_id: str
    approval_type: str
    requester_id: str
    status: str
    input_artifact_hash: str
    policy_version: str
    binding: dict[str, Any]
    binding_hash: str
    requested_at: datetime
    decided_at: datetime | None
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    decision_id: str
    approval_id: str
    approver_id: str
    decision: str
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalToken:
    token_id: str
    approval_id: str
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None
    consumed_by: str | None
    revoked_at: datetime | None
    revoked_reason: str | None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    audit_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    run_id: str | None
    payload: dict[str, Any]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    outbox_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    dispatched_at: datetime | None
