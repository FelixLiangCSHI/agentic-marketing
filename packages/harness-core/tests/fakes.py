"""Shared fixtures: fake tools, fake approval verifier, fake agents."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, StrictStr

from harness_core.context import ArtifactRef
from harness_core.hooks import AuditRecord, InMemoryAuditSink
from harness_core.permissions import PermissionGate
from harness_core.tools import ToolRegistry, ToolResult, ToolSpec


class DraftParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    topic: StrictStr


class PublishParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    package_id: StrictStr


class BudgetParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    amount: int


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _draft_handler(params: BaseModel) -> ToolResult:
    assert isinstance(params, DraftParams)
    ref = ArtifactRef(
        uri="memory://artifacts/draft-1", sha256="sha256:" + "a" * 64, summary="draft"
    )
    return ToolResult(ok=True, value={"topic": params.topic}, evidence={"draft": ref})


def _publish_handler(params: BaseModel) -> ToolResult:
    ref = ArtifactRef(
        uri="memory://artifacts/pub-1", sha256="sha256:" + "b" * 64, summary="published"
    )
    return ToolResult(ok=True, evidence={"published": ref})


def _campaign_handler(params: BaseModel) -> ToolResult:
    ref = ArtifactRef(
        uri="memory://artifacts/plan-1", sha256="sha256:" + "c" * 64, summary="plan"
    )
    return ToolResult(ok=True, evidence={"plan": ref})


def _forbidden_handler(params: BaseModel) -> ToolResult:
    raise AssertionError("L4 handler must never execute")


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="content.draft",
            version="1.0.0",
            level="L1",
            agent_allowlist=frozenset({"content"}),
            params_model=DraftParams,
            handler=_draft_handler,
        )
    )
    registry.register(
        ToolSpec(
            name="content.publish",
            version="1.0.0",
            level="L3",
            agent_allowlist=frozenset({"content"}),
            params_model=PublishParams,
            handler=_publish_handler,
        )
    )
    registry.register(
        ToolSpec(
            name="campaign.plan",
            version="1.0.0",
            level="L1",
            agent_allowlist=frozenset({"campaign"}),
            params_model=NoParams,
            handler=_campaign_handler,
        )
    )
    registry.register(
        ToolSpec(
            name="campaign.delete_production",
            version="1.0.0",
            level="L4",
            agent_allowlist=frozenset({"campaign"}),
            params_model=NoParams,
            handler=_forbidden_handler,
        )
    )
    registry.freeze()
    return registry


@dataclass
class FakeApprovalVerifier:
    valid_tokens: set[str] = field(default_factory=set)
    consumed: list[str] = field(default_factory=list)

    def consume(self, token: str, *, tool_name: str, agent_type: str) -> bool:
        if token in self.valid_tokens:
            self.valid_tokens.remove(token)
            self.consumed.append(token)
            return True
        return False


def build_gate(
    registry: ToolRegistry, verifier: FakeApprovalVerifier | None = None
) -> tuple[PermissionGate, FakeApprovalVerifier]:
    verifier = verifier or FakeApprovalVerifier()
    return (
        PermissionGate(registry, approval_verifier=verifier),
        verifier,
    )


class FailingAuditSink:
    def append(self, record: AuditRecord) -> None:
        raise RuntimeError("audit store unavailable")


__all__ = [
    "BudgetParams",
    "DraftParams",
    "FailingAuditSink",
    "FakeApprovalVerifier",
    "InMemoryAuditSink",
    "NoParams",
    "PublishParams",
    "build_gate",
    "build_registry",
]
