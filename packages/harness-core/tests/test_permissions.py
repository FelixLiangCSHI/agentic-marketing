"""deny -> policy -> approval gate behavior."""

from __future__ import annotations

from harness_core.permissions import PermissionGate

from tests.fakes import FakeApprovalVerifier, build_gate, build_registry


def test_unregistered_tool_denied_at_deny_layer() -> None:
    gate, _ = build_gate(build_registry())
    decision = gate.evaluate(agent_type="content", tool_name="shell.exec", approval_token=None)
    assert not decision.allowed
    assert decision.layer == "deny"


def test_deny_list_wins_over_everything() -> None:
    registry = build_registry()
    verifier = FakeApprovalVerifier(valid_tokens={"tok"})
    gate = PermissionGate(
        registry, approval_verifier=verifier, denied_tools=frozenset({"content.draft"})
    )
    decision = gate.evaluate(agent_type="content", tool_name="content.draft", approval_token="tok")
    assert not decision.allowed
    assert decision.layer == "deny"


def test_l4_always_denied() -> None:
    gate, _ = build_gate(build_registry())
    decision = gate.evaluate(
        agent_type="campaign", tool_name="campaign.delete_production", approval_token="any"
    )
    assert not decision.allowed
    assert decision.layer == "deny"


def test_cross_agent_tool_denied_by_policy() -> None:
    gate, _ = build_gate(build_registry())
    decision = gate.evaluate(agent_type="campaign", tool_name="content.draft", approval_token=None)
    assert not decision.allowed
    assert decision.layer == "policy"


def test_l1_allowed_by_policy() -> None:
    gate, _ = build_gate(build_registry())
    decision = gate.evaluate(agent_type="content", tool_name="content.draft", approval_token=None)
    assert decision.allowed
    assert decision.layer == "policy"


def test_l3_without_token_denied() -> None:
    gate, _ = build_gate(build_registry())
    decision = gate.evaluate(agent_type="content", tool_name="content.publish", approval_token=None)
    assert not decision.allowed
    assert decision.layer == "approval"


def test_l3_with_invalid_token_denied() -> None:
    gate, _ = build_gate(build_registry())
    decision = gate.evaluate(
        agent_type="content", tool_name="content.publish", approval_token="i-say-i-am-approved"
    )
    assert not decision.allowed
    assert decision.layer == "approval"


def test_l3_token_single_use() -> None:
    registry = build_registry()
    verifier = FakeApprovalVerifier(valid_tokens={"tok-1"})
    gate = PermissionGate(registry, approval_verifier=verifier)
    first = gate.evaluate(agent_type="content", tool_name="content.publish", approval_token="tok-1")
    second = gate.evaluate(
        agent_type="content", tool_name="content.publish", approval_token="tok-1"
    )
    assert first.allowed and first.layer == "approval"
    assert not second.allowed and second.layer == "approval"
    assert verifier.consumed == ["tok-1"]
