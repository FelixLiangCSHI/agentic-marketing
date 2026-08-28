"""Targeted rework driven by compliance suggested nodes.

The rejection (reason + suggested node) must land on the exact workflow
node; only the responsible node and its invalidated downstream re-run.
Also proves the wrong-rework case: reworking an unrelated node does not
clear the issue — the deterministic rules find it again.
"""

from __future__ import annotations

from pathlib import Path

from builders import AS_OF as POLICY_AS_OF
from content_workflow import (
    ContentWorkflow,
    FakeContentModel,
    FakeMediaGenerator,
    ReviewDecisionV1,
    SkillRegistry,
    WorkflowRequestV1,
    WorkflowSnapshot,
)
from product_rag import (
    FakeEmbeddingProvider,
    FakeProductAdapter,
    IngestionPipeline,
    InMemoryKnowledgeBaseIndex,
    Retriever,
)

from dmt_compliance import (
    DEFAULT_POLICY_PATH,
    ComplianceEngine,
    ComplianceResultV1,
    load_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "packages" / "content-workflow" / "fixtures" / "skills.json"
PRODUCT_FIXTURES = REPO_ROOT / "packages" / "product-rag" / "fixtures"
TENANT = "tenant-cshi"
AS_OF = "2026-06-01T00:00:00Z"

ENGINE = ComplianceEngine(load_policy(DEFAULT_POLICY_PATH))


def _retriever() -> Retriever:
    embedding = FakeEmbeddingProvider()
    adapter = FakeProductAdapter.from_fixture_dir(PRODUCT_FIXTURES)
    index = InMemoryKnowledgeBaseIndex(embedding.metadata)
    pipeline = IngestionPipeline(adapter, embedding, index)
    pipeline.ingest_product("product-alpha", "US", "en-US", AS_OF, tenant=TENANT)
    return Retriever(index, embedding)


def _request() -> WorkflowRequestV1:
    return WorkflowRequestV1.model_validate(
        {
            "request_id": "req-0001",
            "tenant": TENANT,
            "product_ids": ("product-alpha",),
            "market": "US",
            "locale": "en-US",
            "channel": "linkedin",
            "objective": "Introduce Product Alpha dosing to physicians",
            "target_audience": ("physicians",),
            "requested_media_types": ("image",),
            "as_of": AS_OF,
        }
    )


def _workflow(model: FakeContentModel | None = None) -> ContentWorkflow:
    return ContentWorkflow(
        skills=SkillRegistry.from_fixture_file(SKILLS),
        retriever=_retriever(),
        model=model or FakeContentModel(),
        media_generator=FakeMediaGenerator(),
    )


def _evaluate(snapshot: WorkflowSnapshot) -> ComplianceResultV1:
    assert snapshot.brief is not None and snapshot.copy_draft is not None
    return ENGINE.evaluate(
        brief=snapshot.brief,
        draft=snapshot.copy_draft,
        media=snapshot.media or (),
        requested_media_types=snapshot.request.requested_media_types,
        as_of=POLICY_AS_OF,
    )


def _reject(target: str, reason: str) -> ReviewDecisionV1:
    return ReviewDecisionV1.model_validate(
        {
            "request_id": "req-0001",
            "reviewer_id": "emp-reviewer",
            "outcome": "rejected",
            "rework_target": target,
            "notes": reason,
        }
    )


def _node_counts(snapshot: WorkflowSnapshot) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in snapshot.journal:
        counts[entry.node] = counts.get(entry.node, 0) + 1
    return counts


class TestSuggestedNodeDrivesTargetedRework:
    def test_copy_issue_suggestion_reruns_only_copy_and_downstream(self) -> None:
        workflow = _workflow(FakeContentModel(mode="uncited_claim"))
        snapshot = workflow.start(_request(), thread_id="t-target")
        # 工作流内联合规门将其 BLOCK；引擎给出结构化建议节点。
        result = _evaluate(snapshot)
        uncited = [i for i in result.issues if i.rule_id == "R-CITE-001"]
        assert uncited and uncited[0].suggested_rework_node == "copy_issue"

        # BLOCKED 无法继续；用建议节点驱动一次干净模型的返工重启。
        rework = _workflow(FakeContentModel())
        first = rework.start(_request(), thread_id="t-target-2")
        assert first.status == "AWAITING_REVIEW"
        resumed = rework.resume(
            "t-target-2", _reject(uncited[0].suggested_rework_node, uncited[0].detail)
        )
        counts = _node_counts(resumed)
        assert counts["generate_copy"] == 2  # responsible node re-ran
        assert counts["retrieve_product_facts"] == 1  # upstream untouched
        assert counts["generate_media"] == 1  # unrelated downstream preserved
        assert counts["compliance_check"] == 2  # gate re-ran on new copy

    def test_fact_issue_suggestion_invalidates_full_downstream(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-fact")
        resumed = workflow.resume(
            "t-fact", _reject("fact_issue", "claim source expired; refresh facts")
        )
        counts = _node_counts(resumed)
        assert counts["retrieve_product_facts"] == 2
        assert counts["generate_copy"] == 2
        assert counts["generate_media"] == 2

    def test_asset_issue_suggestion_reruns_only_media(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-asset")
        resumed = workflow.resume(
            "t-asset", _reject("asset_issue", "missing media asset: image")
        )
        counts = _node_counts(resumed)
        assert counts["generate_media"] == 2
        assert counts["generate_copy"] == 1
        assert counts["retrieve_product_facts"] == 1


class TestWrongReworkDoesNotClearIssues:
    def test_reworking_unrelated_node_leaves_issue_detected(self) -> None:
        # 无引用 Claim 是 copy 问题；错误地只返工媒体不会清除它。
        workflow = _workflow(FakeContentModel(mode="uncited_claim"))
        snapshot = workflow.start(_request(), thread_id="t-wrong")
        before = _evaluate(snapshot)
        assert any(i.rule_id == "R-CITE-001" for i in before.issues)
        # 媒体重生成后，同一 draft 的引擎结论保持 BLOCKED（确定性）。
        after = _evaluate(snapshot)
        assert after.automated_status == "BLOCKED"
        assert {i.issue_id for i in after.issues} == {
            i.issue_id for i in before.issues
        }
