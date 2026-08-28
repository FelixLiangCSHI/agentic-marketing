"""Typed Tool Registry.

Every tool declares a pydantic parameter schema, a handler, a permission
level, an agent allowlist, and a version. The registry is frozen before any
run; runtime registration (e.g. a model asking for a wider tool set) raises.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from harness_core.context import ArtifactRef
from harness_core.errors import ToolRegistrationError, ToolValidationError

PermissionLevel = Literal["L0", "L1", "L2", "L3", "L4"]
AgentType = Literal["content", "campaign"]

_LEVELS: tuple[PermissionLevel, ...] = ("L0", "L1", "L2", "L3", "L4")


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Small typed result; large payloads must travel as artifact refs."""

    ok: bool
    value: Mapping[str, Any] = field(default_factory=dict)
    evidence: Mapping[str, ArtifactRef] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    version: str
    level: PermissionLevel
    agent_allowlist: frozenset[AgentType]
    params_model: type[BaseModel]
    handler: Callable[[BaseModel], ToolResult]
    description: str = ""


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._frozen = False

    def register(self, spec: ToolSpec) -> None:
        if self._frozen:
            raise ToolRegistrationError(
                "tool registry is frozen; tools cannot be added at runtime"
            )
        if spec.level not in _LEVELS:
            raise ToolRegistrationError(f"unknown permission level {spec.level!r}")
        if not spec.name or not spec.version:
            raise ToolRegistrationError("tool name and version are required")
        if not spec.agent_allowlist:
            raise ToolRegistrationError(f"tool {spec.name!r} must allowlist at least one agent")
        if spec.name in self._specs:
            raise ToolRegistrationError(f"tool {spec.name!r} is already registered")
        self._specs[spec.name] = spec

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def validate_params(self, name: str, params: Mapping[str, Any]) -> BaseModel:
        spec = self._specs.get(name)
        if spec is None:
            raise ToolValidationError(f"tool {name!r} is not registered")
        try:
            return spec.params_model.model_validate(dict(params))
        except ValidationError as exc:
            messages = "; ".join(
                f"{'/'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
            )
            raise ToolValidationError(f"invalid parameters for tool {name!r}: {messages}") from exc

    def snapshot(self) -> list[dict[str, Any]]:
        """Evidence-friendly registry snapshot (no handlers, no secrets)."""
        return [
            {
                "name": spec.name,
                "version": spec.version,
                "level": spec.level,
                "agent_allowlist": sorted(spec.agent_allowlist),
                "params_schema": spec.params_model.model_json_schema(),
            }
            for spec in sorted(self._specs.values(), key=lambda s: s.name)
        ]
