"""Repositories: the only write path to the persistence schema.

Every repository method returns frozen domain objects; SQLAlchemy sessions,
rows, and SQL never leak to callers (API handlers or agents). Mutations are
made inside the caller's :class:`~dmt_api.persistence.uow.UnitOfWork`
transaction so state change + run event + audit + outbox commit atomically.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import false, func, or_, select, update
from sqlalchemy.orm import Session, aliased

from dmt_api.persistence.domain import (
    ApprovalRequest,
    ApprovalToken,
    AuditEvent,
    JournalEntry,
    OutboxMessage,
    Run,
    RunEvent,
    Task,
)
from dmt_api.persistence.errors import (
    ApprovalExpiredError,
    BindingMismatchError,
    DependencyCycleError,
    LeaseConflictError,
    NotFoundError,
    SeparationOfDutiesError,
    TokenConsumptionError,
)
from dmt_api.persistence.orm import (
    ApprovalDecisionRow,
    ApprovalRequestRow,
    ApprovalTokenRow,
    AuditEventRow,
    JournalRow,
    OutboxRow,
    RunEventRow,
    RunRow,
    TaskDependencyRow,
    TaskRow,
)
from dmt_api.persistence.transitions import (
    APPROVAL_TRANSITIONS,
    RUN_TRANSITIONS,
    TASK_TRANSITIONS,
    ensure_transition,
)

_TERMINAL_RUN_STATUSES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "COMPENSATED"})


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _hash_token(plaintext: str) -> str:
    return "sha256:" + hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _same_timezone(left: datetime, right: datetime) -> tuple[datetime, datetime]:
    if left.tzinfo is None and right.tzinfo is not None:
        return left.replace(tzinfo=right.tzinfo), right
    if left.tzinfo is not None and right.tzinfo is None:
        return left, right.replace(tzinfo=left.tzinfo)
    return left, right


def _run_to_domain(row: RunRow) -> Run:
    return Run(
        run_id=row.run_id,
        parent_run_id=row.parent_run_id,
        agent_type=row.agent_type,
        workflow_name=row.workflow_name,
        workflow_version=row.workflow_version,
        tenant=row.tenant,
        business_unit=row.business_unit,
        requester_id=row.requester_id,
        environment=row.environment,
        status=row.status,
        version=row.version,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _task_to_domain(row: TaskRow) -> Task:
    return Task(
        task_id=row.task_id,
        run_id=row.run_id,
        task_type=row.task_type,
        status=row.status,
        attempt=row.attempt,
        max_attempts=row.max_attempts,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        version=row.version,
        created_at=row.created_at,
    )


def _approval_to_domain(row: ApprovalRequestRow) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=row.approval_id,
        run_id=row.run_id,
        approval_type=row.approval_type,
        requester_id=row.requester_id,
        status=row.status,
        input_artifact_hash=row.input_artifact_hash,
        policy_version=row.policy_version,
        binding=dict(row.binding),
        binding_hash=row.binding_hash,
        requested_at=row.requested_at,
        decided_at=row.decided_at,
        expires_at=row.expires_at,
    )


def _token_to_domain(row: ApprovalTokenRow) -> ApprovalToken:
    return ApprovalToken(
        token_id=row.token_id,
        approval_id=row.approval_id,
        token_hash=row.token_hash,
        issued_at=row.issued_at,
        expires_at=row.expires_at,
        consumed_at=row.consumed_at,
        consumed_by=row.consumed_by,
        revoked_at=row.revoked_at,
        revoked_reason=row.revoked_reason,
    )


class _BaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _append_run_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> RunEventRow:
        self._locked_run(run_id)
        next_sequence = self._session.execute(
            select(func.coalesce(func.max(RunEventRow.sequence) + 1, 0)).where(
                RunEventRow.run_id == run_id
            )
        ).scalar_one()
        row = RunEventRow(
            event_id=_new_id("evt"),
            run_id=run_id,
            sequence=next_sequence,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
        )
        self._session.add(row)
        return row

    def _append_audit(
        self,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        run_id: str | None,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        self._session.add(
            AuditEventRow(
                audit_id=_new_id("aud"),
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                run_id=run_id,
                payload=payload,
                occurred_at=occurred_at,
            )
        )

    def _append_outbox(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: datetime,
    ) -> None:
        self._session.add(
            OutboxRow(
                outbox_id=_new_id("obx"),
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
                created_at=created_at,
            )
        )

    def _locked_run(self, run_id: str) -> RunRow:
        row = self._session.get(RunRow, run_id, with_for_update=True)
        if row is None:
            raise NotFoundError(f"run {run_id!r} does not exist")
        return row


class RunRepository(_BaseRepository):
    def create(
        self,
        *,
        run_id: str,
        parent_run_id: str | None,
        agent_type: str,
        workflow_name: str,
        workflow_version: str,
        tenant: str,
        business_unit: str,
        requester_id: str,
        environment: str,
        actor_id: str,
        created_at: datetime,
    ) -> Run:
        row = RunRow(
            run_id=run_id,
            parent_run_id=parent_run_id,
            agent_type=agent_type,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            tenant=tenant,
            business_unit=business_unit,
            requester_id=requester_id,
            environment=environment,
            status="CREATED",
            version=0,
            created_at=created_at,
            started_at=None,
            finished_at=None,
        )
        self._session.add(row)
        self._session.flush()
        payload = {"from_status": None, "to_status": "CREATED"}
        self._append_run_event(run_id, "RUN_STATUS_CHANGED", payload, created_at)
        self._append_audit(
            actor_id, "run.created", "run", run_id, run_id, payload, created_at
        )
        self._append_outbox("run", run_id, "RUN_STATUS_CHANGED", payload, created_at)
        return _run_to_domain(row)

    def get(self, run_id: str) -> Run | None:
        row = self._session.get(RunRow, run_id)
        return None if row is None else _run_to_domain(row)

    def transition(
        self, run_id: str, new_status: str, *, actor_id: str, occurred_at: datetime
    ) -> Run:
        row = self._locked_run(run_id)
        ensure_transition(RUN_TRANSITIONS, f"run {run_id}", row.status, new_status)
        payload = {"from_status": row.status, "to_status": new_status}
        row.status = new_status
        row.version += 1
        if new_status == "RUNNING" and row.started_at is None:
            row.started_at = occurred_at
        if new_status in _TERMINAL_RUN_STATUSES and row.finished_at is None:
            row.finished_at = occurred_at
        self._append_run_event(run_id, "RUN_STATUS_CHANGED", payload, occurred_at)
        self._append_audit(
            actor_id, "run.status_changed", "run", run_id, run_id, payload, occurred_at
        )
        self._append_outbox("run", run_id, "RUN_STATUS_CHANGED", payload, occurred_at)
        self._session.flush()
        return _run_to_domain(row)


class RunEventRepository(_BaseRepository):
    def for_run(self, run_id: str) -> list[RunEvent]:
        rows = self._session.scalars(
            select(RunEventRow)
            .where(RunEventRow.run_id == run_id)
            .order_by(RunEventRow.sequence)
        ).all()
        return [
            RunEvent(
                event_id=row.event_id,
                run_id=row.run_id,
                sequence=row.sequence,
                event_type=row.event_type,
                payload=row.payload,
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]


class TaskRepository(_BaseRepository):
    def create(
        self,
        *,
        task_id: str,
        run_id: str,
        task_type: str,
        max_attempts: int,
        actor_id: str,
        created_at: datetime,
    ) -> Task:
        self._locked_run(run_id)
        row = TaskRow(
            task_id=task_id,
            run_id=run_id,
            task_type=task_type,
            status="PENDING",
            attempt=0,
            max_attempts=max_attempts,
            lease_owner=None,
            lease_expires_at=None,
            version=0,
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()
        payload = {"task_id": task_id, "from_status": None, "to_status": "PENDING"}
        self._append_run_event(run_id, "TASK_STATUS_CHANGED", payload, created_at)
        self._append_audit(
            actor_id, "task.created", "task", task_id, run_id, payload, created_at
        )
        self._append_outbox("task", task_id, "TASK_STATUS_CHANGED", payload, created_at)
        return _task_to_domain(row)

    def get(self, task_id: str) -> Task | None:
        row = self._session.get(TaskRow, task_id)
        return None if row is None else _task_to_domain(row)

    def dependencies(self, task_id: str) -> list[str]:
        return list(
            self._session.scalars(
                select(TaskDependencyRow.depends_on_task_id)
                .where(TaskDependencyRow.task_id == task_id)
                .order_by(TaskDependencyRow.depends_on_task_id)
            ).all()
        )

    def add_dependency(self, task_id: str, depends_on_task_id: str) -> None:
        if task_id == depends_on_task_id:
            raise DependencyCycleError(f"task {task_id!r} cannot depend on itself")
        task = self._session.get(TaskRow, task_id, with_for_update=True)
        if task is None:
            raise NotFoundError(f"task {task_id!r} does not exist")
        depends_on = self._session.get(TaskRow, depends_on_task_id, with_for_update=True)
        if depends_on is None:
            raise NotFoundError(f"task {depends_on_task_id!r} does not exist")
        if depends_on.run_id != task.run_id:
            raise DependencyCycleError(
                f"dependency {task_id!r} -> {depends_on_task_id!r} crosses run boundaries"
            )
        # Serialize DAG writes per run so concurrent inserts cannot sneak a
        # cycle past the reachability check.
        self._locked_run(task.run_id)
        if self._is_reachable(start=depends_on_task_id, target=task_id):
            raise DependencyCycleError(
                f"dependency {task_id!r} -> {depends_on_task_id!r} would create a cycle"
            )
        self._session.add(
            TaskDependencyRow(task_id=task_id, depends_on_task_id=depends_on_task_id)
        )
        self._session.flush()

    def _is_reachable(self, *, start: str, target: str) -> bool:
        dep = TaskDependencyRow
        base = (
            select(dep.depends_on_task_id.label("node"))
            .where(dep.task_id == start)
            .cte("reachable", recursive=True)
        )
        alias = aliased(dep)
        base = base.union(
            select(alias.depends_on_task_id).join(base, alias.task_id == base.c.node)
        )
        result = self._session.execute(
            select(func.count()).select_from(base).where(base.c.node == target)
        ).scalar_one()
        return bool(result)

    def transition(
        self, task_id: str, new_status: str, *, actor_id: str, occurred_at: datetime
    ) -> Task:
        row = self._session.get(TaskRow, task_id, with_for_update=True)
        if row is None:
            raise NotFoundError(f"task {task_id!r} does not exist")
        ensure_transition(TASK_TRANSITIONS, f"task {task_id}", row.status, new_status)
        payload = {"task_id": task_id, "from_status": row.status, "to_status": new_status}
        row.status = new_status
        row.version += 1
        if new_status != "LEASED":
            row.lease_owner = None
            row.lease_expires_at = None
        self._append_run_event(row.run_id, "TASK_STATUS_CHANGED", payload, occurred_at)
        self._append_audit(
            actor_id, "task.status_changed", "task", task_id, row.run_id, payload, occurred_at
        )
        self._append_outbox("task", task_id, "TASK_STATUS_CHANGED", payload, occurred_at)
        self._session.flush()
        return _task_to_domain(row)

    def claim(
        self,
        task_id: str,
        *,
        owner_id: str,
        now: datetime,
        lease_seconds: int,
        expected_version: int,
    ) -> Task:
        return self._conditional_claim(
            task_id,
            owner_id=owner_id,
            now=now,
            lease_seconds=lease_seconds,
            expected_version=expected_version,
            required_status="READY",
            require_expired_lease=False,
        )

    def reclaim_expired(
        self,
        task_id: str,
        *,
        owner_id: str,
        now: datetime,
        lease_seconds: int,
        expected_version: int,
    ) -> Task:
        return self._conditional_claim(
            task_id,
            owner_id=owner_id,
            now=now,
            lease_seconds=lease_seconds,
            expected_version=expected_version,
            required_status="LEASED",
            require_expired_lease=True,
        )

    def _conditional_claim(
        self,
        task_id: str,
        *,
        owner_id: str,
        now: datetime,
        lease_seconds: int,
        expected_version: int,
        required_status: str,
        require_expired_lease: bool,
    ) -> Task:
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        stmt = (
            update(TaskRow)
            .where(
                TaskRow.task_id == task_id,
                TaskRow.status == required_status,
                TaskRow.version == expected_version,
                TaskRow.attempt < TaskRow.max_attempts,
            )
            .values(
                status="LEASED",
                lease_owner=owner_id,
                lease_expires_at=lease_expires_at,
                attempt=TaskRow.attempt + 1,
                version=TaskRow.version + 1,
            )
            .returning(TaskRow)
        )
        if require_expired_lease:
            stmt = stmt.where(TaskRow.lease_expires_at < now)
        row = self._session.scalars(stmt).one_or_none()
        if row is None:
            raise LeaseConflictError(
                f"task {task_id!r} could not be claimed by {owner_id!r} "
                f"(status/version/lease conflict)"
            )
        payload = {
            "task_id": task_id,
            "from_status": required_status,
            "to_status": "LEASED",
            "lease_owner": owner_id,
        }
        self._append_run_event(row.run_id, "TASK_STATUS_CHANGED", payload, now)
        self._append_audit(owner_id, "task.claimed", "task", task_id, row.run_id, payload, now)
        self._append_outbox("task", task_id, "TASK_STATUS_CHANGED", payload, now)
        self._session.flush()
        return _task_to_domain(row)


class JournalRepository(_BaseRepository):
    def append(
        self,
        *,
        journal_id: str,
        run_id: str,
        node_name: str,
        payload: dict[str, Any],
        recorded_at: datetime,
    ) -> JournalEntry:
        self._locked_run(run_id)
        next_sequence = self._session.execute(
            select(func.coalesce(func.max(JournalRow.sequence) + 1, 0)).where(
                JournalRow.run_id == run_id
            )
        ).scalar_one()
        row = JournalRow(
            journal_id=journal_id,
            run_id=run_id,
            sequence=next_sequence,
            node_name=node_name,
            payload=payload,
            recorded_at=recorded_at,
        )
        self._session.add(row)
        self._session.flush()
        return JournalEntry(
            journal_id=row.journal_id,
            run_id=row.run_id,
            sequence=row.sequence,
            node_name=row.node_name,
            payload=row.payload,
            recorded_at=row.recorded_at,
        )

    def for_run(self, run_id: str) -> list[JournalEntry]:
        rows = self._session.scalars(
            select(JournalRow).where(JournalRow.run_id == run_id).order_by(JournalRow.sequence)
        ).all()
        return [
            JournalEntry(
                journal_id=row.journal_id,
                run_id=row.run_id,
                sequence=row.sequence,
                node_name=row.node_name,
                payload=row.payload,
                recorded_at=row.recorded_at,
            )
            for row in rows
        ]


class ApprovalRepository(_BaseRepository):
    def create_request(
        self,
        *,
        approval_id: str,
        run_id: str,
        approval_type: str,
        requester_id: str,
        input_artifact_hash: str,
        policy_version: str,
        requested_at: datetime,
        expires_at: datetime,
        token_id: str,
        binding: dict[str, Any] | None = None,
        binding_hash: str = "",
        tool_name: str = "",
        agent_type: str = "",
    ) -> tuple[ApprovalRequest, str]:
        """Create a PENDING approval request and issue its single-use token.

        Returns the request and the plaintext token. Only the SHA-256 hash of
        the token is stored; the plaintext is returned exactly once and must
        be delivered to the approver out of band.
        """
        self._locked_run(run_id)
        row = ApprovalRequestRow(
            approval_id=approval_id,
            run_id=run_id,
            approval_type=approval_type,
            requester_id=requester_id,
            status="PENDING",
            input_artifact_hash=input_artifact_hash,
            policy_version=policy_version,
            binding=binding or {},
            binding_hash=binding_hash,
            tool_name=tool_name,
            agent_type=agent_type,
            requested_at=requested_at,
            decided_at=None,
            expires_at=expires_at,
            version=0,
        )
        self._session.add(row)
        token_plaintext = secrets.token_urlsafe(32)
        self._session.add(
            ApprovalTokenRow(
                token_id=token_id,
                approval_id=approval_id,
                token_hash=_hash_token(token_plaintext),
                issued_at=requested_at,
                expires_at=expires_at,
                consumed_at=None,
                consumed_by=None,
            )
        )
        self._session.flush()
        payload = {"approval_id": approval_id, "approval_type": approval_type}
        self._append_run_event(run_id, "APPROVAL_REQUESTED", payload, requested_at)
        self._append_audit(
            requester_id, "approval.requested", "approval", approval_id, run_id, payload,
            requested_at,
        )
        self._append_outbox("approval", approval_id, "APPROVAL_REQUESTED", payload, requested_at)
        return _approval_to_domain(row), token_plaintext

    def get(self, approval_id: str) -> ApprovalRequest | None:
        row = self._session.get(ApprovalRequestRow, approval_id)
        return None if row is None else _approval_to_domain(row)

    def get_token(self, token_id: str) -> ApprovalToken | None:
        row = self._session.get(ApprovalTokenRow, token_id)
        return None if row is None else _token_to_domain(row)

    def decide(
        self,
        *,
        approval_id: str,
        decision_id: str,
        approver_id: str,
        decision: str,
        decided_at: datetime,
    ) -> ApprovalRequest:
        row = self._session.get(ApprovalRequestRow, approval_id, with_for_update=True)
        if row is None:
            raise NotFoundError(f"approval {approval_id!r} does not exist")
        if approver_id == row.requester_id:
            raise SeparationOfDutiesError(
                f"approver {approver_id!r} cannot decide their own request {approval_id!r}"
            )
        ensure_transition(
            APPROVAL_TRANSITIONS, f"approval {approval_id}", row.status, decision
        )
        expires_at, decision_time = _same_timezone(row.expires_at, decided_at)
        if decision_time >= expires_at:
            raise ApprovalExpiredError(f"approval {approval_id!r} has expired")
        self._session.add(
            ApprovalDecisionRow(
                decision_id=decision_id,
                approval_id=approval_id,
                approver_id=approver_id,
                decision=decision,
                decided_at=decided_at,
            )
        )
        row.status = decision
        row.decided_at = decided_at
        row.version += 1
        payload = {"approval_id": approval_id, "decision": decision}
        self._append_run_event(row.run_id, "APPROVAL_DECIDED", payload, decided_at)
        self._append_audit(
            approver_id, "approval.decided", "approval", approval_id, row.run_id, payload,
            decided_at,
        )
        self._append_outbox("approval", approval_id, "APPROVAL_DECIDED", payload, decided_at)
        self._session.flush()
        return _approval_to_domain(row)

    def consume_token(self, token_plaintext: str, *, consumed_by: str, now: datetime) -> ApprovalToken:
        """Atomically consume a token; exactly one consumer can ever win."""
        stmt = (
            update(ApprovalTokenRow)
            .where(
                ApprovalTokenRow.token_hash == _hash_token(token_plaintext),
                ApprovalTokenRow.consumed_at.is_(None),
                ApprovalTokenRow.revoked_at.is_(None),
                ApprovalTokenRow.expires_at > now,
            )
            .values(consumed_at=now, consumed_by=consumed_by)
            .returning(ApprovalTokenRow)
        )
        row = self._session.scalars(stmt).one_or_none()
        if row is None:
            raise TokenConsumptionError(
                "approval token is unknown, expired, or already consumed"
            )
        payload = {"approval_id": row.approval_id, "token_id": row.token_id}
        self._append_audit(
            consumed_by, "approval.token_consumed", "approval_token", row.token_id, None,
            payload, now,
        )
        self._session.flush()
        return _token_to_domain(row)

    def consume_token_bound(
        self,
        token_plaintext: str,
        *,
        consumed_by: str,
        now: datetime,
        expected_binding_hash: str,
        expected_tool_name: str = "",
        expected_agent_type: str = "",
    ) -> ApprovalToken:
        """Consume a token only for an APPROVED request with a matching binding.

        A binding mismatch burns the token (revokes it) so it can never be
        replayed against the original input either.
        """
        token_row = self._session.scalars(
            select(ApprovalTokenRow)
            .where(ApprovalTokenRow.token_hash == _hash_token(token_plaintext))
            .with_for_update()
        ).one_or_none()
        if (
            token_row is None
            or token_row.consumed_at is not None
            or token_row.revoked_at is not None
            or token_row.expires_at <= now
        ):
            raise TokenConsumptionError(
                "approval token is unknown, expired, revoked, or already consumed"
            )
        approval = self._session.get(
            ApprovalRequestRow, token_row.approval_id, with_for_update=True
        )
        if approval is None or approval.status != "APPROVED":
            raise TokenConsumptionError(
                "approval token is not backed by an APPROVED request"
            )
        if (
            approval.binding_hash != expected_binding_hash
            or approval.tool_name != expected_tool_name
            or approval.agent_type != expected_agent_type
        ):
            token_row.revoked_at = now
            token_row.revoked_reason = "binding_mismatch"
            self._append_audit(
                consumed_by,
                "approval.token_revoked",
                "approval_token",
                token_row.token_id,
                approval.run_id,
                {"approval_id": approval.approval_id, "reason": "binding_mismatch"},
                now,
            )
            self._session.flush()
            raise BindingMismatchError(
                "approval token was minted for a different input binding; token revoked"
            )
        token_row.consumed_at = now
        token_row.consumed_by = consumed_by
        payload = {"approval_id": approval.approval_id, "token_id": token_row.token_id}
        self._append_audit(
            consumed_by, "approval.token_consumed", "approval_token",
            token_row.token_id, approval.run_id, payload, now,
        )
        self._session.flush()
        return _token_to_domain(token_row)

    def revoke_request(
        self, approval_id: str, *, actor_id: str, reason: str, now: datetime
    ) -> ApprovalRequest:
        """Revoke a request and burn its token (e.g. incident or input change)."""
        # Lock order matches consume_token_bound (token before approval) so
        # concurrent consume/revoke can never deadlock.
        token_row = self._session.scalars(
            select(ApprovalTokenRow)
            .where(ApprovalTokenRow.approval_id == approval_id)
            .with_for_update()
        ).one_or_none()
        row = self._session.get(ApprovalRequestRow, approval_id, with_for_update=True)
        if row is None:
            raise NotFoundError(f"approval {approval_id!r} does not exist")
        ensure_transition(
            APPROVAL_TRANSITIONS, f"approval {approval_id}", row.status, "REVOKED"
        )
        row.status = "REVOKED"
        row.decided_at = now
        row.version += 1
        if token_row is not None and token_row.revoked_at is None:
            token_row.revoked_at = now
            token_row.revoked_reason = reason
        payload = {"approval_id": approval_id, "reason": reason}
        self._append_run_event(row.run_id, "APPROVAL_DECIDED", payload, now)
        self._append_audit(
            actor_id, "approval.revoked", "approval", approval_id, row.run_id,
            payload, now,
        )
        self._append_outbox("approval", approval_id, "APPROVAL_DECIDED", payload, now)
        self._session.flush()
        return _approval_to_domain(row)

    def list_recent(
        self,
        *,
        limit: int = 100,
        tenant: str | None = None,
        run_id: str | None = None,
        requester_id: str | None = None,
        approver_approval_types: frozenset[str] = frozenset(),
    ) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequestRow)
        if tenant is not None:
            stmt = stmt.join(
                RunRow, ApprovalRequestRow.run_id == RunRow.run_id
            ).where(RunRow.tenant == tenant)
        if run_id is not None:
            stmt = stmt.where(ApprovalRequestRow.run_id == run_id)
        scope_predicates = []
        if requester_id is not None:
            scope_predicates.append(ApprovalRequestRow.requester_id == requester_id)
        if approver_approval_types:
            scope_predicates.append(
                ApprovalRequestRow.approval_type.in_(approver_approval_types)
            )
        if scope_predicates:
            stmt = stmt.where(or_(*scope_predicates))
        elif requester_id is not None:
            stmt = stmt.where(false())
        rows = self._session.scalars(
            stmt.order_by(ApprovalRequestRow.requested_at.desc()).limit(limit)
        ).all()
        return [_approval_to_domain(row) for row in rows]


class AuditRepository(_BaseRepository):
    def append(
        self,
        *,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        run_id: str | None,
        payload: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        self._append_audit(
            actor_id, action, resource_type, resource_id, run_id, payload, occurred_at
        )

    def for_run(self, run_id: str) -> list[AuditEvent]:
        rows = self._session.scalars(
            select(AuditEventRow)
            .where(AuditEventRow.run_id == run_id)
            .order_by(AuditEventRow.occurred_at, AuditEventRow.audit_id)
        ).all()
        return [
            AuditEvent(
                audit_id=row.audit_id,
                actor_id=row.actor_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                run_id=row.run_id,
                payload=row.payload,
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]


class OutboxRepository(_BaseRepository):
    def pending(self) -> list[OutboxMessage]:
        rows = self._session.scalars(
            select(OutboxRow)
            .where(OutboxRow.dispatched_at.is_(None))
            .order_by(OutboxRow.created_at, OutboxRow.outbox_id)
        ).all()
        return [
            OutboxMessage(
                outbox_id=row.outbox_id,
                aggregate_type=row.aggregate_type,
                aggregate_id=row.aggregate_id,
                event_type=row.event_type,
                payload=row.payload,
                created_at=row.created_at,
                dispatched_at=row.dispatched_at,
            )
            for row in rows
        ]

    def claim_pending(self, *, limit: int = 100) -> list[OutboxMessage]:
        """Lease a batch of pending messages with ``FOR UPDATE SKIP LOCKED``.

        Concurrent dispatchers claim disjoint batches: rows locked by
        another transaction are skipped instead of blocking, so multiple
        instances can drain the outbox without double dispatching. The
        lease lasts for the surrounding transaction; call
        :meth:`mark_dispatched` before committing.
        """
        rows = self._session.scalars(
            select(OutboxRow)
            .where(OutboxRow.dispatched_at.is_(None))
            .order_by(OutboxRow.created_at, OutboxRow.outbox_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        return [
            OutboxMessage(
                outbox_id=row.outbox_id,
                aggregate_type=row.aggregate_type,
                aggregate_id=row.aggregate_id,
                event_type=row.event_type,
                payload=row.payload,
                created_at=row.created_at,
                dispatched_at=row.dispatched_at,
            )
            for row in rows
        ]

    def mark_dispatched(self, outbox_id: str, *, dispatched_at: datetime) -> None:
        row = self._session.scalars(
            update(OutboxRow)
            .where(OutboxRow.outbox_id == outbox_id, OutboxRow.dispatched_at.is_(None))
            .values(dispatched_at=dispatched_at)
            .returning(OutboxRow)
        ).one_or_none()
        if row is None:
            raise NotFoundError(f"outbox message {outbox_id!r} is unknown or already dispatched")
