"""Operation ledger contracts: keys, records, statuses and typed errors.

One logical external write per ``(tenant, channel, account_id,
idempotency_key, input_hash)``. Statuses are monotonic: terminal states
never regress, ``UNKNOWN`` can only leave through reconciliation (found →
``RECONCILED``; confirmed-not-created retry → ``SUCCEEDED``; undecidable →
``WAITING_RECONCILIATION`` and ultimately the manual queue/DLQ), and
``FAILED`` is reserved for writes that verifiably never happened.
"""

from __future__ import annotations

from typing import Literal

import pydantic

OperationStatus = Literal[
    "INTENT",
    "SUCCEEDED",
    "UNKNOWN",
    "RECONCILED",
    "WAITING_RECONCILIATION",
    "FAILED",
    "COMPENSATION_PENDING",
]

# from-status -> allowed to-statuses. Re-asserting the current status is a
# no-op everywhere (idempotent replays).
ALLOWED_TRANSITIONS: dict[OperationStatus, frozenset[OperationStatus]] = {
    "INTENT": frozenset({"SUCCEEDED", "UNKNOWN", "FAILED", "COMPENSATION_PENDING"}),
    "UNKNOWN": frozenset({"RECONCILED", "SUCCEEDED", "WAITING_RECONCILIATION"}),
    "WAITING_RECONCILIATION": frozenset({"RECONCILED", "SUCCEEDED"}),
    "SUCCEEDED": frozenset(),
    "RECONCILED": frozenset(),
    "FAILED": frozenset(),
    "COMPENSATION_PENDING": frozenset(),
}


class ActivationError(Exception):
    """Base class for activation pipeline failures."""


class DuplicateOperationError(ActivationError):
    """The idempotency key is already bound to a different input hash."""


class IllegalTransitionError(ActivationError):
    """The requested status change would violate monotonicity."""


class ApprovalInvalidError(ActivationError):
    """The approval token is unknown, consumed, expired, revoked or unbound."""


class AuditWriteError(ActivationError):
    """Audit or outbox write failed; high-risk actions must fail closed."""


class _Frozen(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class OperationKey(_Frozen):
    """Identity of one logical external write."""

    tenant_id: str = pydantic.Field(min_length=1)
    channel: str = pydantic.Field(min_length=1)
    account_id: str = pydantic.Field(min_length=1)
    idempotency_key: str = pydantic.Field(min_length=1)

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.tenant_id, self.channel, self.account_id, self.idempotency_key)


class OperationRecord(_Frozen):
    """One row of the connector-operations ledger."""

    key: OperationKey
    input_hash: str = pydantic.Field(pattern=r"^sha256:[0-9a-f]{64}$")
    approval_id: str = pydantic.Field(min_length=1)
    status: OperationStatus
    external_object_id: str | None = None
    operation_id: str | None = None
    attempts: int = 0
    created_at: str
    updated_at: str


class CompensationTask(_Frozen):
    """A pending-approval runbook task; never auto-executed (L4)."""

    task_id: str = pydantic.Field(min_length=1)
    key: OperationKey
    created_object_ids: tuple[str, ...] = pydantic.Field(min_length=1)
    reason: str = pydantic.Field(min_length=1)
    requires_approval: Literal[True] = True
    status: Literal["PENDING_APPROVAL"] = "PENDING_APPROVAL"
    created_at: str
