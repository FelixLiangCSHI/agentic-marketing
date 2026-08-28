"""State machines for Run and Task statuses.

The transition tables are the single source of truth used by repositories;
they mirror the enums frozen in the v1 contracts (``dmt_api.contracts``).
"""

from __future__ import annotations

from dmt_api.persistence.errors import IllegalStateTransitionError

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"PLANNING", "RUNNING", "FAILED", "CANCELLED"}),
    "PLANNING": frozenset({"RUNNING", "WAITING_APPROVAL", "FAILED", "CANCELLED"}),
    "RUNNING": frozenset(
        {
            "WAITING_TOOL",
            "WAITING_APPROVAL",
            "RETRY_SCHEDULED",
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
            "COMPENSATING",
        }
    ),
    "WAITING_TOOL": frozenset({"RUNNING", "RETRY_SCHEDULED", "FAILED", "CANCELLED"}),
    "WAITING_APPROVAL": frozenset({"RUNNING", "FAILED", "CANCELLED"}),
    "RETRY_SCHEDULED": frozenset({"RUNNING", "FAILED", "CANCELLED"}),
    "COMPENSATING": frozenset({"COMPENSATED", "FAILED"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
    "COMPENSATED": frozenset(),
}

TASK_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"READY", "CANCELLED"}),
    "READY": frozenset({"LEASED", "CANCELLED"}),
    "LEASED": frozenset({"RUNNING", "READY", "FAILED", "CANCELLED"}),
    "RUNNING": frozenset({"SUCCEEDED", "FAILED", "READY", "CANCELLED"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}

APPROVAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"APPROVED", "REJECTED", "EXPIRED", "REVOKED"}),
    "APPROVED": frozenset({"REVOKED"}),
    "REJECTED": frozenset(),
    "EXPIRED": frozenset(),
    "REVOKED": frozenset(),
}


def ensure_transition(
    machine: dict[str, frozenset[str]], entity: str, current: str, target: str
) -> None:
    allowed = machine.get(current)
    if allowed is None:
        raise IllegalStateTransitionError(f"{entity}: unknown status {current!r}")
    if target not in allowed:
        raise IllegalStateTransitionError(
            f"{entity}: transition {current!r} -> {target!r} is not allowed"
        )
