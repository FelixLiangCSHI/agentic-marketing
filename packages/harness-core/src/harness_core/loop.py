"""The harness loop: one run, host-enforced security, full timeline.

Flow per run: on_input -> [before_model -> action]* -> before_stop ->
goal check -> after_run. Tool calls pass the fixed hook order and the
deny -> policy -> approval gate; denials and errors are fed back to the
model as typed observations, never executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from harness_core.context import ArtifactRef
from harness_core.errors import (
    AuditUnavailableError,
    ModelOutputError,
    ToolExecutionError,
    ToolValidationError,
)
from harness_core.goal import GoalSpec, check_goal
from harness_core.hooks import AuditSink, HookRunner
from harness_core.model import FakeModel, Observation, StopAction, ToolCallAction
from harness_core.permissions import Decision, PermissionGate
from harness_core.tools import AgentType, ToolRegistry

RunStatus = Literal["SUCCEEDED", "FAILED"]


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    step: int
    kind: str  # "input" | "model_action" | "permission" | "tool_result" | "tool_error" | "goal" | "run_finished"
    detail: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentConfig:
    agent_type: AgentType
    registry: ToolRegistry
    gate: PermissionGate
    goal: GoalSpec
    max_steps: int = 16


@dataclass(frozen=True, slots=True)
class RunReport:
    run_id: str
    agent_type: AgentType
    status: RunStatus
    reason: str
    timeline: tuple[TimelineEvent, ...]
    denied_decisions: tuple[Decision, ...]
    evidence: dict[str, ArtifactRef]


class HarnessLoop:
    def __init__(self, *, audit_sink: AuditSink) -> None:
        self._audit_sink = audit_sink

    def run(self, config: AgentConfig, model: FakeModel, *, run_id: str) -> RunReport:
        if not config.registry.frozen:
            raise ToolExecutionError("tool registry must be frozen before a run starts")
        hooks = HookRunner(run_id=run_id, audit_sink=self._audit_sink)
        timeline: list[TimelineEvent] = []
        denied: list[Decision] = []
        evidence: dict[str, ArtifactRef] = {}
        step = 0

        def record(kind: str, detail: dict[str, Any]) -> None:
            timeline.append(TimelineEvent(step=step, kind=kind, detail=detail))

        def finish(status: RunStatus, reason: str) -> RunReport:
            record("run_finished", {"status": status, "reason": reason})
            hooks.fire("after_run", {"status": status, "reason": reason})
            return RunReport(
                run_id=run_id,
                agent_type=config.agent_type,
                status=status,
                reason=reason,
                timeline=tuple(timeline),
                denied_decisions=tuple(denied),
                evidence=dict(evidence),
            )

        observation = Observation(kind="input", payload={})

        try:
            hooks.fire("on_input", {"agent_type": config.agent_type})
            record("input", {"agent_type": config.agent_type})
            while True:
                step += 1
                if step > config.max_steps:
                    hooks.fire("before_stop", {"reason": "max_steps_exceeded"})
                    return finish("FAILED", "max_steps_exceeded")

                hooks.fire("before_model", {"step": step})
                try:
                    action = model.next_action(observation)
                except ModelOutputError as exc:
                    record("model_action", {"error": str(exc)})
                    hooks.fire("before_stop", {"reason": "model_output_error"})
                    return finish("FAILED", f"model_output_error: {exc}")

                if isinstance(action, StopAction):
                    record("model_action", {"action": "stop", "reason": action.reason})
                    hooks.fire("before_stop", {"reason": action.reason})
                    goal_result = check_goal(config.goal, evidence)
                    record(
                        "goal",
                        {"passed": goal_result.passed, "missing": list(goal_result.missing)},
                    )
                    if goal_result.passed:
                        return finish("SUCCEEDED", "goal_evidence_complete")
                    return finish(
                        "FAILED",
                        "goal_evidence_missing: " + ", ".join(goal_result.missing),
                    )

                record(
                    "model_action",
                    {"action": "tool_call", "tool_name": action.tool_name},
                )
                hooks.fire("before_tool", {"tool_name": action.tool_name})

                decision = config.gate.evaluate(
                    agent_type=config.agent_type,
                    tool_name=action.tool_name,
                    approval_token=action.approval_token,
                )
                record(
                    "permission",
                    {
                        "tool_name": action.tool_name,
                        "allowed": decision.allowed,
                        "layer": decision.layer,
                        "reason": decision.reason,
                    },
                )
                if not decision.allowed:
                    denied.append(decision)
                    hooks.fire(
                        "on_tool_error",
                        {"tool_name": action.tool_name, "denied": True, "reason": decision.reason},
                    )
                    observation = Observation(
                        kind="tool_denied",
                        payload={"tool_name": action.tool_name, "reason": decision.reason},
                    )
                    continue

                try:
                    params = config.registry.validate_params(action.tool_name, action.params)
                    spec = config.registry.get(action.tool_name)
                    assert spec is not None
                    result = spec.handler(params)
                except (ToolValidationError, ToolExecutionError) as exc:
                    record("tool_error", {"tool_name": action.tool_name, "error": str(exc)})
                    hooks.fire(
                        "on_tool_error",
                        {"tool_name": action.tool_name, "denied": False, "error": str(exc)},
                    )
                    observation = Observation(
                        kind="tool_error",
                        payload={"tool_name": action.tool_name, "error": str(exc)},
                    )
                    continue

                if result.ok:
                    evidence.update(result.evidence)
                record(
                    "tool_result",
                    {
                        "tool_name": action.tool_name,
                        "ok": result.ok,
                        "evidence_keys": sorted(result.evidence),
                    },
                )
                hooks.fire("after_tool", {"tool_name": action.tool_name, "ok": result.ok})
                observation = Observation(
                    kind="tool_result",
                    payload={"tool_name": action.tool_name, "ok": result.ok, **result.value},
                )
        except AuditUnavailableError as exc:
            # Fail closed: no further tool execution, run is failed. The
            # audit sink itself is down, so we cannot fire more hooks.
            timeline.append(
                TimelineEvent(step=step, kind="run_finished", detail={"status": "FAILED", "reason": str(exc)})
            )
            return RunReport(
                run_id=run_id,
                agent_type=config.agent_type,
                status="FAILED",
                reason=f"audit_unavailable: {exc}",
                timeline=tuple(timeline),
                denied_decisions=tuple(denied),
                evidence=dict(evidence),
            )
