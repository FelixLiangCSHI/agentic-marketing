"""Fixed hook order with mandatory audit.

Order (frozen): on_input -> before_model -> (before_tool ->
(after_tool | on_tool_error) -> before_model)* -> before_stop -> after_run.
A host-forced stop (max steps, guardrail) may follow a tool outcome directly.

Every hook firing writes one audit record. If the audit sink fails, the hook
raises AuditUnavailableError and the caller must fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from harness_core.errors import AuditUnavailableError, HookOrderError

Hook = Literal[
    "on_input",
    "before_model",
    "before_tool",
    "after_tool",
    "on_tool_error",
    "before_stop",
    "after_run",
]

HOOK_ORDER: tuple[Hook, ...] = (
    "on_input",
    "before_model",
    "before_tool",
    "after_tool",
    "on_tool_error",
    "before_stop",
    "after_run",
)

_ALLOWED_TRANSITIONS: dict[Hook | None, frozenset[Hook]] = {
    None: frozenset({"on_input"}),
    "on_input": frozenset({"before_model"}),
    "before_model": frozenset({"before_tool", "before_stop"}),
    "before_tool": frozenset({"after_tool", "on_tool_error"}),
    "after_tool": frozenset({"before_model", "before_stop"}),
    "on_tool_error": frozenset({"before_model", "before_stop"}),
    "before_stop": frozenset({"after_run"}),
    "after_run": frozenset(),
}


@dataclass(frozen=True, slots=True)
class AuditRecord:
    sequence: int
    run_id: str
    hook: Hook
    payload: dict[str, Any]


class AuditSink(Protocol):
    def append(self, record: AuditRecord) -> None: ...


@dataclass
class InMemoryAuditSink:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


class HookRunner:
    """Enforces the frozen hook order and audits every hook firing."""

    def __init__(self, *, run_id: str, audit_sink: AuditSink) -> None:
        self._run_id = run_id
        self._audit_sink = audit_sink
        self._last: Hook | None = None
        self._sequence = 0

    @property
    def last(self) -> Hook | None:
        return self._last

    def fire(self, hook: Hook, payload: dict[str, Any]) -> None:
        allowed = _ALLOWED_TRANSITIONS[self._last]
        if hook not in allowed:
            raise HookOrderError(
                f"hook {hook!r} cannot follow {self._last!r}; allowed: {sorted(allowed)}"
            )
        record = AuditRecord(
            sequence=self._sequence, run_id=self._run_id, hook=hook, payload=payload
        )
        try:
            self._audit_sink.append(record)
        except Exception as exc:  # audit unavailable -> fail closed upstream
            raise AuditUnavailableError(f"audit sink failed at hook {hook!r}") from exc
        self._last = hook
        self._sequence += 1
