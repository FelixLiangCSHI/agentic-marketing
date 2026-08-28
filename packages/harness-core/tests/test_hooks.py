"""Hook order enforcement and mandatory audit."""

from __future__ import annotations

import pytest

from harness_core.errors import AuditUnavailableError, HookOrderError
from harness_core.hooks import HOOK_ORDER, HookRunner, InMemoryAuditSink

from tests.fakes import FailingAuditSink


def test_hook_order_constant_is_frozen() -> None:
    assert HOOK_ORDER == (
        "on_input",
        "before_model",
        "before_tool",
        "after_tool",
        "on_tool_error",
        "before_stop",
        "after_run",
    )


def test_legal_sequence_passes_and_audits_every_hook() -> None:
    sink = InMemoryAuditSink()
    runner = HookRunner(run_id="run-1", audit_sink=sink)
    sequence = [
        "on_input",
        "before_model",
        "before_tool",
        "after_tool",
        "before_model",
        "before_tool",
        "on_tool_error",
        "before_model",
        "before_stop",
        "after_run",
    ]
    for hook in sequence:
        runner.fire(hook, {})  # type: ignore[arg-type]
    assert [record.hook for record in sink.records] == sequence
    assert [record.sequence for record in sink.records] == list(range(len(sequence)))


@pytest.mark.parametrize(
    "sequence",
    [
        ["before_model"],  # must start with on_input
        ["on_input", "before_tool"],  # tool before model
        ["on_input", "before_model", "after_tool"],  # result without call
        ["on_input", "before_model", "before_tool", "before_stop"],  # skip tool outcome
        ["on_input", "before_model", "before_stop", "after_run", "on_input"],  # after terminal
    ],
)
def test_illegal_sequences_raise(sequence: list[str]) -> None:
    runner = HookRunner(run_id="run-1", audit_sink=InMemoryAuditSink())
    with pytest.raises(HookOrderError):
        for hook in sequence:
            runner.fire(hook, {})  # type: ignore[arg-type]


def test_audit_failure_raises_and_blocks_progress() -> None:
    runner = HookRunner(run_id="run-1", audit_sink=FailingAuditSink())
    with pytest.raises(AuditUnavailableError):
        runner.fire("on_input", {})
    assert runner.last is None  # hook did not advance without audit
