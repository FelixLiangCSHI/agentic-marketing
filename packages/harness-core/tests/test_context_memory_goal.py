"""Context minimality, memory isolation, and goal check."""

from __future__ import annotations

import pytest

from harness_core.context import ArtifactRef, ContextPacker, InMemoryArtifactStore
from harness_core.errors import MemoryPolicyError
from harness_core.goal import GoalSpec, check_goal
from harness_core.memory import MemoryNamespace, MemoryStore


def test_small_value_stays_inline() -> None:
    packer = ContextPacker(InMemoryArtifactStore(), max_inline_bytes=2048)
    value = {"headline": "short"}
    assert packer.pack(value, summary="headline") == value


def test_large_value_becomes_artifact_ref() -> None:
    store = InMemoryArtifactStore()
    packer = ContextPacker(store, max_inline_bytes=64)
    packed = packer.pack({"body": "x" * 500}, summary="long body")
    assert isinstance(packed, ArtifactRef)
    assert packed.uri.startswith("memory://artifacts/")
    assert packed.sha256.startswith("sha256:")
    assert packed.summary == "long body"
    assert store.payloads is not None and packed.uri in store.payloads


def test_memory_rejects_non_allowlisted_key() -> None:
    store = MemoryStore(allowed_keys=frozenset({"tone"}))
    ns = MemoryNamespace(agent_type="content", user_id="u1", brand="b1", market="de")
    with pytest.raises(MemoryPolicyError):
        store.put(ns, "run_transcript", "...")


def test_memory_rejects_oversized_value() -> None:
    store = MemoryStore(allowed_keys=frozenset({"tone"}))
    ns = MemoryNamespace(agent_type="content", user_id="u1", brand="b1", market="de")
    with pytest.raises(MemoryPolicyError):
        store.put(ns, "tone", "x" * 4096)


def test_memory_is_isolated_per_namespace() -> None:
    store = MemoryStore(allowed_keys=frozenset({"tone"}))
    content_ns = MemoryNamespace(agent_type="content", user_id="u1", brand="b1", market="de")
    campaign_ns = MemoryNamespace(agent_type="campaign", user_id="u1", brand="b1", market="de")
    other_user = MemoryNamespace(agent_type="content", user_id="u2", brand="b1", market="de")
    other_market = MemoryNamespace(agent_type="content", user_id="u1", brand="b1", market="fr")
    store.put(content_ns, "tone", "formal")
    assert store.get(content_ns, "tone") == "formal"
    assert store.get(campaign_ns, "tone") is None
    assert store.get(other_user, "tone") is None
    assert store.get(other_market, "tone") is None


def test_goal_fails_without_evidence() -> None:
    spec = GoalSpec(required_evidence=frozenset({"draft", "review"}))
    result = check_goal(spec, {})
    assert not result.passed
    assert result.missing == ("draft", "review")


def test_goal_passes_with_all_evidence_and_does_not_mutate() -> None:
    spec = GoalSpec(required_evidence=frozenset({"draft"}))
    ref = ArtifactRef(uri="memory://a/1", sha256="sha256:" + "a" * 64, summary="d")
    evidence = {"draft": ref}
    result = check_goal(spec, evidence)
    assert result.passed and result.missing == ()
    assert evidence == {"draft": ref}
