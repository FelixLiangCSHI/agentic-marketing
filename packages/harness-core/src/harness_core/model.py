"""Typed model actions and the scripted FakeModel (Phase 01: fakes only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from harness_core.errors import ModelOutputError


@dataclass(frozen=True, slots=True)
class ToolCallAction:
    tool_name: str
    params: Mapping[str, Any] = field(default_factory=dict)
    approval_token: str | None = None


@dataclass(frozen=True, slots=True)
class StopAction:
    reason: str = "done"


ModelAction = ToolCallAction | StopAction


@dataclass(frozen=True, slots=True)
class Observation:
    """What the host feeds back to the model after each step."""

    kind: str  # "input" | "tool_result" | "tool_denied" | "tool_error"
    payload: Mapping[str, Any]


class FakeModel:
    """Deterministic scripted model. Raises typed errors on bad scripts."""

    def __init__(self, script: Sequence[ModelAction | object]) -> None:
        self._script = list(script)
        self._cursor = 0
        self.observations: list[Observation] = []

    def next_action(self, observation: Observation) -> ModelAction:
        self.observations.append(observation)
        if self._cursor >= len(self._script):
            raise ModelOutputError("fake model script exhausted without a stop action")
        action = self._script[self._cursor]
        self._cursor += 1
        if not isinstance(action, (ToolCallAction, StopAction)):
            raise ModelOutputError(
                f"model output {type(action).__name__} cannot be parsed into a typed action"
            )
        return action
