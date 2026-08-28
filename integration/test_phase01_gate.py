"""Phase 01 / Subphase 08 — integration quality gate (fakes only).

Integrates harness-core + infra-core and demonstrates the full Fake
dual-agent lifecycle plus every mandated fault injection. No new features;
this suite only exercises what Subphases 01-07 delivered.

Run: pip install -e "packages/harness-core[dev]" -e "packages/infra-core[dev]"
     python -m pytest integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ConfigDict, StrictStr

from harness_core.context import ArtifactRef
from harness_core.errors import MemoryPolicyError
from harness_core.hooks import AuditRecord, InMemoryAuditSink
from harness_core.goal import GoalSpec
from harness_core.loop import AgentConfig, HarnessLoop, RunReport
from harness_core.memory import MemoryNamespace, MemoryStore
from harness_core.model import FakeModel, StopAction, ToolCallAction
from harness_core.permissions import PermissionGate
from harness_core.tools import ToolRegistry, ToolResult, ToolSpec
from infra_core.clock import FakeClock
from infra_core.queue import FakeQueueClient, RetryPolicy
from infra_core.secrets import FakeSecretResolver, SecretNotFoundError, SecretRef

# ---------------------------------------------------------------------------
# Shared fakes: two agents, isolated tool sets / memory / credentials.
# ---------------------------------------------------------------------------


class DraftParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    topic: StrictStr


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _evidence(name: str, marker: str) -> ToolResult:
    ref = ArtifactRef(
        uri=f"memory://integration/{name}",
        sha256="sha256:" + marker * 64,
        summary=name,
    )
    return ToolResult(ok=True, evidence={name: ref})


def _malicious_handler(params: BaseModel) -> ToolResult:
    raise AssertionError("gated handler must never execute")


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="content.draft",
            version="1.0.0",
            level="L1",
            agent_allowlist=frozenset({"content"}),
            params_model=DraftParams,
            handler=lambda params: _evidence("draft", "a"),
        )
    )
    registry.register(
        ToolSpec(
            name="content.publish",
            version="1.0.0",
            level="L3",
            agent_allowlist=frozenset({"content"}),
            params_model=NoParams,
            handler=lambda params: _evidence("published", "b"),
        )
    )
    registry.register(
        ToolSpec(
            name="campaign.plan",
            version="1.0.0",
            level="L1",
            agent_allowlist=frozenset({"campaign"}),
            params_model=NoParams,
            handler=lambda params: _evidence("plan", "c"),
        )
    )
    registry.register(
        ToolSpec(
            name="campaign.activate",
            version="1.0.0",
            level="L3",
            agent_allowlist=frozenset({"campaign"}),
            params_model=NoParams,
            handler=lambda params: _evidence("activated", "d"),
        )
    )
    registry.register(
        ToolSpec(
            name="campaign.delete_production",
            version="1.0.0",
            level="L4",
            agent_allowlist=frozenset({"campaign"}),
            params_model=NoParams,
            handler=_malicious_handler,
        )
    )
    registry.freeze()
    return registry


@dataclass
class FakeApprovalVerifier:
    """One-time tokens bound to (tool_name, agent_type)."""

    tokens: dict[str, tuple[str, str]] = field(default_factory=dict)

    def grant(self, token: str, *, tool_name: str, agent_type: str) -> None:
        self.tokens[token] = (tool_name, agent_type)

    def consume(self, token: str, *, tool_name: str, agent_type: str) -> bool:
        if self.tokens.get(token) != (tool_name, agent_type):
            return False
        del self.tokens[token]
        return True


def run_agent(
    agent_type: str,
    required: frozenset[str],
    model: FakeModel,
    *,
    verifier: FakeApprovalVerifier | None = None,
    audit_sink: object | None = None,
) -> RunReport:
    registry = build_registry()
    config = AgentConfig(
        agent_type=agent_type,  # type: ignore[arg-type]
        registry=registry,
        gate=PermissionGate(registry, approval_verifier=verifier or FakeApprovalVerifier()),
        goal=GoalSpec(required_evidence=required),
    )
    loop = HarnessLoop(audit_sink=audit_sink or InMemoryAuditSink())  # type: ignore[arg-type]
    return loop.run(config, model, run_id=f"it-{agent_type}")


def make_queue(clock: FakeClock, *, max_attempts: int = 3) -> FakeQueueClient:
    return FakeQueueClient(
        clock=clock,
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
            jitter_ratio=0.1,
        ),
        lease_seconds=30,
    )


START = datetime(2026, 8, 28, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Fake dual-agent demo: create / execute / wait approval / reject /
#    approve / resume / cancel.
# ---------------------------------------------------------------------------


class TestDualAgentDemo:
    def test_content_lifecycle_reject_then_approve_then_resume(self) -> None:
        clock = FakeClock(START)
        queue = make_queue(clock)
        verifier = FakeApprovalVerifier()

        # Create: task enters the queue once.
        queue.enqueue("content.tasks", {"topic": "launch"}, idempotency_key="task-1")
        message = queue.receive("content.tasks", worker_id="w1")
        assert message is not None

        # Execute until approval is required: L3 without a token pauses the
        # side effect (denied, never executed) — this is the WAITING state.
        waiting = run_agent(
            "content",
            frozenset({"draft", "published"}),
            FakeModel(
                [
                    ToolCallAction("content.draft", {"topic": "launch"}),
                    ToolCallAction("content.publish", {}),
                    StopAction(),
                ]
            ),
            verifier=verifier,
        )
        assert waiting.status == "FAILED"
        assert any(d.layer == "approval" for d in waiting.denied_decisions)
        assert "published" not in waiting.evidence
        # Worker re-queues the task for a later attempt instead of acking.
        queue.nack(message, reason="waiting_for_approval")

        # Reject: a rejected approval never mints a token; retry still denied.
        clock.advance(timedelta(seconds=5))
        message = queue.receive("content.tasks", worker_id="w1")
        assert message is not None and message.attempt == 2
        rejected = run_agent(
            "content",
            frozenset({"draft", "published"}),
            FakeModel(
                [
                    ToolCallAction("content.draft", {"topic": "launch"}),
                    ToolCallAction("content.publish", {}, approval_token="rejected-token"),
                    StopAction(),
                ]
            ),
            verifier=verifier,
        )
        assert rejected.status == "FAILED"
        assert "published" not in rejected.evidence
        queue.nack(message, reason="approval_rejected_retry_later")

        # Approve + resume: a granted one-time token lets the run finish.
        verifier.grant("ok-token", tool_name="content.publish", agent_type="content")
        clock.advance(timedelta(seconds=10))
        message = queue.receive("content.tasks", worker_id="w2")
        assert message is not None and message.attempt == 3
        resumed = run_agent(
            "content",
            frozenset({"draft", "published"}),
            FakeModel(
                [
                    ToolCallAction("content.draft", {"topic": "launch"}),
                    ToolCallAction("content.publish", {}, approval_token="ok-token"),
                    StopAction(),
                ]
            ),
            verifier=verifier,
        )
        assert resumed.status == "SUCCEEDED"
        assert set(resumed.evidence) == {"draft", "published"}
        queue.ack(message)
        assert queue.pending_count("content.tasks") == 0
        # The token was consumed exactly once.
        assert verifier.tokens == {}

    def test_campaign_lifecycle_and_cancellation(self) -> None:
        clock = FakeClock(START)
        queue = make_queue(clock)
        verifier = FakeApprovalVerifier()
        verifier.grant("go", tool_name="campaign.activate", agent_type="campaign")

        report = run_agent(
            "campaign",
            frozenset({"plan", "activated"}),
            FakeModel(
                [
                    ToolCallAction("campaign.plan", {}),
                    ToolCallAction("campaign.activate", {}, approval_token="go"),
                    StopAction(),
                ]
            ),
            verifier=verifier,
        )
        assert report.status == "SUCCEEDED"

        # Cancel: a cancelled task is never delivered to any worker.
        queue.enqueue("campaign.tasks", {"plan": "q4"}, idempotency_key="task-c1")
        queue.cancel("campaign.tasks", idempotency_key="task-c1")
        assert queue.receive("campaign.tasks", worker_id="w1") is None


# ---------------------------------------------------------------------------
# 2. Namespace isolation: tools, memory, credentials.
# ---------------------------------------------------------------------------


class TestNamespaceIsolation:
    def test_cross_agent_tool_access_is_denied(self) -> None:
        for agent, foreign_tool in (
            ("content", "campaign.plan"),
            ("campaign", "content.draft"),
        ):
            report = run_agent(
                agent,
                frozenset(),
                FakeModel([ToolCallAction(foreign_tool, {"topic": "x"} if "draft" in foreign_tool else {}), StopAction()]),
            )
            assert report.denied_decisions, f"{agent} must not use {foreign_tool}"
            assert report.denied_decisions[0].layer == "policy"

    def test_memory_namespaces_do_not_leak(self) -> None:
        store = MemoryStore(allowed_keys=frozenset({"tone"}))
        content_ns = MemoryNamespace(agent_type="content", user_id="u1", brand="b", market="de")
        campaign_ns = MemoryNamespace(agent_type="campaign", user_id="u1", brand="b", market="de")
        store.put(content_ns, "tone", "formal")
        assert store.get(campaign_ns, "tone") is None
        with pytest.raises(MemoryPolicyError):
            store.put(content_ns, "run_state", "not-allowed")

    def test_credential_namespaces_are_separate(self) -> None:
        content_secrets = FakeSecretResolver({"secretref://vault/content/llm": "synthetic-1"})
        campaign_secrets = FakeSecretResolver({"secretref://vault/campaign/linkedin": "synthetic-2"})
        ref = SecretRef.parse("secretref://vault/content/llm")
        assert content_secrets.resolve(ref).reveal() == "synthetic-1"
        with pytest.raises(SecretNotFoundError):
            campaign_secrets.resolve(ref)


# ---------------------------------------------------------------------------
# 3. Fault injection.
# ---------------------------------------------------------------------------


class FailingAuditSink:
    def append(self, record: AuditRecord) -> None:
        raise RuntimeError("audit store unavailable")


class TestFaultInjection:
    def test_illegal_state_unfrozen_registry_rejected(self) -> None:
        registry = ToolRegistry()  # never frozen -> illegal run state
        config = AgentConfig(
            agent_type="content",
            registry=registry,
            gate=PermissionGate(registry, approval_verifier=FakeApprovalVerifier()),
            goal=GoalSpec(required_evidence=frozenset()),
        )
        loop = HarnessLoop(audit_sink=InMemoryAuditSink())
        with pytest.raises(Exception, match="frozen"):
            loop.run(config, FakeModel([StopAction()]), run_id="it-illegal")

    def test_l3_without_approval_and_l4_never_execute(self) -> None:
        report = run_agent(
            "campaign",
            frozenset(),
            FakeModel(
                [
                    ToolCallAction("campaign.activate", {}),
                    ToolCallAction("campaign.delete_production", {}),
                    StopAction(),
                ]
            ),
        )
        layers = [d.layer for d in report.denied_decisions]
        assert layers == ["approval", "deny"]
        assert report.evidence == {}

    def test_malicious_unregistered_tool_is_denied(self) -> None:
        report = run_agent(
            "content",
            frozenset(),
            FakeModel([ToolCallAction("shell.exec", {}), StopAction()]),
        )
        assert report.denied_decisions[0].layer == "deny"

    def test_audit_failure_fails_closed(self) -> None:
        report = run_agent(
            "content",
            frozenset({"draft"}),
            FakeModel([ToolCallAction("content.draft", {"topic": "x"}), StopAction()]),
            audit_sink=FailingAuditSink(),
        )
        assert report.status == "FAILED"
        assert "audit_unavailable" in report.reason
        assert report.evidence == {}

    def test_duplicate_messages_produce_one_side_effect(self) -> None:
        clock = FakeClock(START)
        queue = make_queue(clock)
        for _ in range(100):
            queue.enqueue("content.tasks", {"topic": "dup"}, idempotency_key="dup-1")
        assert queue.pending_count("content.tasks") == 1
        processed = 0
        message = queue.receive("content.tasks", worker_id="w1")
        while message is not None:
            processed += 1
            queue.ack(message)
            message = queue.receive("content.tasks", worker_id="w1")
        assert processed == 1
        # Re-enqueue after completion stays deduplicated.
        queue.enqueue("content.tasks", {"topic": "dup"}, idempotency_key="dup-1")
        assert queue.pending_count("content.tasks") == 0

    def test_worker_restart_redelivers_with_attempt_bump(self) -> None:
        clock = FakeClock(START)
        queue = make_queue(clock)
        queue.enqueue("content.tasks", {"topic": "crash"}, idempotency_key="crash-1")
        first = queue.receive("content.tasks", worker_id="w1")
        assert first is not None and first.attempt == 1
        # Worker crashes: no ack, lease expires.
        clock.advance(timedelta(seconds=31))
        second = queue.receive("content.tasks", worker_id="w2")
        assert second is not None and second.attempt == 2
        assert second.idempotency_key == "crash-1"
        queue.ack(second)

    def test_poison_message_lands_in_dlq_and_can_replay(self) -> None:
        clock = FakeClock(START)
        queue = make_queue(clock, max_attempts=2)
        queue.enqueue("content.tasks", {"topic": "poison"}, idempotency_key="poison-1")
        for _ in range(2):
            message = queue.receive("content.tasks", worker_id="w1")
            assert message is not None
            queue.nack(message, reason="handler exploded")
            clock.advance(timedelta(seconds=120))
        assert queue.receive("content.tasks", worker_id="w1") is None
        dead = queue.dlq("content.tasks")
        assert len(dead) == 1 and dead[0].last_error == "handler exploded"
        assert queue.replay_dlq("content.tasks") == 1
        replayed = queue.receive("content.tasks", worker_id="w1")
        assert replayed is not None and replayed.idempotency_key == "poison-1"
