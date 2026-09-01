"""Operation store, audit log, outbox and compensation queue.

Protocols plus deterministic in-memory fakes. The PostgreSQL projection of
the same ledger lives in ``apps/api`` (``campaign.connector_operations`` /
``campaign.compensation_tasks`` migrations); this module is the single
source of the transition rules either implementation must satisfy.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from campaign_activation.models import (
    ALLOWED_TRANSITIONS,
    AuditWriteError,
    CompensationTask,
    DuplicateOperationError,
    IllegalTransitionError,
    OperationKey,
    OperationRecord,
    OperationStatus,
)


class OperationStore(Protocol):
    """Ledger of logical external writes."""

    def begin(
        self, *, key: OperationKey, input_hash: str, approval_id: str, now: str
    ) -> tuple[OperationRecord, bool]: ...

    def get(self, key: OperationKey) -> OperationRecord | None: ...

    def transition(
        self,
        *,
        key: OperationKey,
        to: OperationStatus,
        now: str,
        external_object_id: str | None = None,
        operation_id: str | None = None,
    ) -> OperationRecord: ...


@dataclass
class FakeOperationStore:
    """In-memory ledger enforcing uniqueness and monotonic transitions."""

    _records: dict[tuple[str, str, str, str], OperationRecord] = field(default_factory=dict)

    def begin(
        self, *, key: OperationKey, input_hash: str, approval_id: str, now: str
    ) -> tuple[OperationRecord, bool]:
        existing = self._records.get(key.as_tuple())
        if existing is not None:
            if existing.input_hash != input_hash:
                raise DuplicateOperationError(
                    "idempotency key is already bound to a different input_hash; "
                    "refusing to overwrite the recorded operation"
                )
            return existing, False
        record = OperationRecord(
            key=key,
            input_hash=input_hash,
            approval_id=approval_id,
            status="INTENT",
            created_at=now,
            updated_at=now,
        )
        self._records[key.as_tuple()] = record
        return record, True

    def get(self, key: OperationKey) -> OperationRecord | None:
        return self._records.get(key.as_tuple())

    def transition(
        self,
        *,
        key: OperationKey,
        to: OperationStatus,
        now: str,
        external_object_id: str | None = None,
        operation_id: str | None = None,
    ) -> OperationRecord:
        record = self._records.get(key.as_tuple())
        if record is None:
            raise KeyError(f"no operation recorded for {key.as_tuple()!r}")
        if to != record.status and to not in ALLOWED_TRANSITIONS[record.status]:
            raise IllegalTransitionError(
                f"illegal operation transition {record.status} -> {to}"
            )
        updated = record.model_copy(
            update={
                "status": to,
                "updated_at": now,
                "attempts": record.attempts + 1,
                "external_object_id": (
                    external_object_id
                    if external_object_id is not None
                    else record.external_object_id
                ),
                "operation_id": (
                    operation_id if operation_id is not None else record.operation_id
                ),
            }
        )
        self._records[key.as_tuple()] = updated
        return updated

    def records(self) -> tuple[OperationRecord, ...]:
        return tuple(self._records.values())


class AuditLog(Protocol):
    def record(self, event: Mapping[str, Any]) -> None: ...


@dataclass
class FakeAuditLog:
    """Append-only audit sink; ``fail``/``fail_after`` simulate outages."""

    fail: bool = False
    fail_after: int | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: Mapping[str, Any]) -> None:
        if self.fail:
            raise AuditWriteError("audit backend unavailable; failing closed")
        if self.fail_after is not None and len(self.events) >= self.fail_after:
            raise AuditWriteError("audit backend unavailable; failing closed")
        self.events.append(dict(event))


class OutboxWriter(Protocol):
    def append(
        self, *, aggregate_id: str, event_type: str, payload: Mapping[str, Any]
    ) -> None: ...


@dataclass
class FakeOutbox:
    """Append-only outbox; entries survive worker crashes for repair jobs."""

    fail: bool = False
    entries: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self, *, aggregate_id: str, event_type: str, payload: Mapping[str, Any]
    ) -> None:
        if self.fail:
            raise AuditWriteError("outbox write failed; failing closed")
        self.entries.append(
            {
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": dict(payload),
            }
        )


class CompensationQueue(Protocol):
    def submit(self, task: CompensationTask) -> None: ...


@dataclass
class FakeCompensationQueue:
    """Collects pending-approval runbook tasks; execution is out of scope."""

    tasks: list[CompensationTask] = field(default_factory=list)
    executed: int = 0  # stays 0 — L4 compensation is never auto-executed

    def submit(self, task: CompensationTask) -> None:
        self.tasks.append(task)


def compensation_task_id(key: OperationKey) -> str:
    digest = hashlib.sha256("|".join(key.as_tuple()).encode("utf-8")).hexdigest()
    return "comp-" + digest[:16]
