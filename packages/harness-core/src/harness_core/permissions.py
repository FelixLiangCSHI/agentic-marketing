"""deny -> policy -> approval three-layer permission gate.

Host code decides; model claims (e.g. "this is approved") are never inputs.
Phase 01 rules: L4 is always denied; L3 requires a host-verified single-use
approval token; L0–L2 pass policy if the agent is allowlisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from harness_core.tools import AgentType, ToolRegistry

Layer = Literal["deny", "policy", "approval"]


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    layer: Layer
    reason: str


class ApprovalVerifier(Protocol):
    """Consumes a single-use approval token; host-side verification only."""

    def consume(self, token: str, *, tool_name: str, agent_type: str) -> bool: ...


class PermissionGate:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        approval_verifier: ApprovalVerifier,
        denied_tools: frozenset[str] = frozenset(),
    ) -> None:
        self._registry = registry
        self._verifier = approval_verifier
        self._denied_tools = denied_tools

    def evaluate(
        self, *, agent_type: AgentType, tool_name: str, approval_token: str | None
    ) -> Decision:
        # Layer 1: deny — hard, non-negotiable denials.
        spec = self._registry.get(tool_name)
        if spec is None:
            return Decision(False, "deny", f"tool {tool_name!r} is not registered")
        if tool_name in self._denied_tools:
            return Decision(False, "deny", f"tool {tool_name!r} is on the deny list")
        if spec.level == "L4":
            return Decision(False, "deny", "L4 tools are always denied in Phase 01")

        # Layer 2: policy — agent allowlist and level policy.
        if agent_type not in spec.agent_allowlist:
            return Decision(
                False, "policy", f"agent {agent_type!r} is not allowlisted for {tool_name!r}"
            )
        if spec.level in ("L0", "L1", "L2"):
            return Decision(True, "policy", f"{spec.level} allowed by policy")

        # Layer 3: approval — L3 requires a valid, unconsumed token.
        if approval_token is None:
            return Decision(False, "approval", f"L3 tool {tool_name!r} requires an approval token")
        if not self._verifier.consume(approval_token, tool_name=tool_name, agent_type=agent_type):
            return Decision(
                False, "approval", f"approval token for {tool_name!r} is invalid or consumed"
            )
        return Decision(True, "approval", f"L3 approved for {tool_name!r}")
