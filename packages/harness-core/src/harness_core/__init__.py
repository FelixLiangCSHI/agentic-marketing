"""Shared dual-agent harness (Phase 01 / Subphase 04).

Minimal trusted loop for the Content and Campaign agents: Loop, typed Tool
Registry, deny -> policy -> approval permission gate, fixed Hook order,
minimal Context, isolated Memory, and evidence-based Goal Check.

Security rules (see ADR-001/003 and the phase prompt):

* Security decisions are made by host code — never by model self-report.
* The tool registry is frozen before any run; nothing can widen it at
  runtime (prompt injection asking for new tools is structurally impossible).
* L3 tools require a host-verified, single-use approval token; L4 tools are
  always denied in Phase 01.
* Every hook is audited; if the audit sink is unavailable, tool execution
  fails closed.
* Goal Check passes only on required evidence artifacts; a model claiming
  success without evidence yields a FAILED run.
"""

from __future__ import annotations

from harness_core.context import ArtifactRef, ContextPacker
from harness_core.goal import GoalResult, GoalSpec
from harness_core.hooks import HOOK_ORDER, HookRunner
from harness_core.loop import AgentConfig, HarnessLoop, RunReport
from harness_core.memory import MemoryNamespace, MemoryStore
from harness_core.model import FakeModel, StopAction, ToolCallAction
from harness_core.permissions import Decision, PermissionGate
from harness_core.tools import ToolRegistry, ToolResult, ToolSpec

__all__ = [
    "HOOK_ORDER",
    "AgentConfig",
    "ArtifactRef",
    "ContextPacker",
    "Decision",
    "FakeModel",
    "GoalResult",
    "GoalSpec",
    "HarnessLoop",
    "HookRunner",
    "MemoryNamespace",
    "MemoryStore",
    "PermissionGate",
    "RunReport",
    "StopAction",
    "ToolCallAction",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
]
