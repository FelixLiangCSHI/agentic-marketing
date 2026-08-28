"""Content Workflow tests: happy path, pause/resume, targeted rework,
cancel, worker restart, typed failures, uncited-claim blocking, draft-only
packaging and goal check.

P2-CP02/P2-CP05 fake-baseline gates covered:
* claim source coverage 100% (uncited claim -> flagged + blocked);
* required brief/review fields 100% (versioned frozen contracts);
* channel hard rules enforced deterministically;
* rework re-runs only the responsible node and its invalidated downstream;
* goal check verifies evidence only; AI cannot self-approve.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_core.goal import check_goal

from content_workflow import (
    CONTENT_GOAL_SPEC,
    CONTENT_WORKFLOW_VERSION,
    ContentWorkflow,
    FakeContentModel,
    FakeMediaGenerator,
    InvalidNodeOutputError,
    ReviewDecisionV1,
    SkillRegistry,
    WorkflowCancelledError,
    WorkflowRequestV1,
    WorkflowSnapshot,
    WorkflowStateError,
    build_goal_evidence,
)
from product_rag import (
    FakeEmbeddingProvider,
    FakeProductAdapter,
    IngestionPipeline,
    InMemoryKnowledgeBaseIndex,
    Retriever,
)

SKILLS = Path(__file__).resolve().parents[1] / "fixtures" / "skills.json"
PRODUCT_FIXTURES = (
    Path(__file__).resolve().parents[2] / "product-rag" / "fixtures"
)
TENANT = "tenant-cshi"
AS_OF = "2026-06-01T00:00:00Z"


def _retriever() -> Retriever:
    embedding = FakeEmbeddingProvider()
    adapter = FakeProductAdapter.from_fixture_dir(PRODUCT_FIXTURES)
    index = InMemoryKnowledgeBaseIndex(embedding.metadata)
    pipeline = IngestionPipeline(adapter, embedding, index)
    pipeline.ingest_product("product-alpha", "US", "en-US", AS_OF, tenant=TENANT)
    pipeline.ingest_product("product-alpha", "US", "de-DE", AS_OF, tenant=TENANT)
    return Retriever(index, embedding)


def _request(**overrides: object) -> WorkflowRequestV1:
    base: dict[str, object] = {
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
    base.update(overrides)
    return WorkflowRequestV1.model_validate(base)


def _workflow(model: FakeContentModel | None = None) -> ContentWorkflow:
    return ContentWorkflow(
        skills=SkillRegistry.from_fixture_file(SKILLS),
        retriever=_retriever(),
        model=model or FakeContentModel(),
        media_generator=FakeMediaGenerator(),
    )


def _approve(request_id: str = "req-0001") -> ReviewDecisionV1:
    return ReviewDecisionV1(
        request_id=request_id,
        reviewer_id="emp-reviewer",
        outcome="approved",
        rework_target=None,
        notes="fixture-approved",
    )


def _reject(target: str | None, request_id: str = "req-0001") -> ReviewDecisionV1:
    return ReviewDecisionV1.model_validate(
        {
            "request_id": request_id,
            "reviewer_id": "emp-reviewer",
            "outcome": "rejected",
            "rework_target": target,
            "notes": "fixture-rejected",
        }
    )


def _node_counts(snapshot: WorkflowSnapshot) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in snapshot.journal:
        counts[entry.node] = counts.get(entry.node, 0) + 1
    return counts


class TestHappyPath:
    def test_pauses_at_human_review_then_packages_on_approval(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(_request(), thread_id="t-happy")
        assert snapshot.status == "AWAITING_REVIEW"
        assert snapshot.copy_draft is not None
        assert snapshot.compliance is not None and snapshot.compliance.passed
        assert snapshot.package is None

        final = workflow.resume("t-happy", _approve())
        assert final.status == "APPROVED_PACKAGED"
        assert final.package is not None
        assert final.package.workflow_version == CONTENT_WORKFLOW_VERSION
        assert final.package.skill_versions == final.skill_versions
        assert _node_counts(final) == {
            "validate_input": 1,
            "retrieve_product_facts": 1,
            "build_brief": 1,
            "generate_copy": 1,
            "generate_media": 1,
            "compliance_check": 1,
            "human_review": 1,
            "package_approved": 1,
        }

    def test_all_copy_claims_carry_citations(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(_request(), thread_id="t-cite")
        assert snapshot.copy_draft is not None and snapshot.copy_draft.claims
        for claim in snapshot.copy_draft.claims:
            assert claim.citation is not None
            assert claim.citation.source_content_hash.startswith("sha256:")

    def test_journal_records_versioned_hashes_for_every_node(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(_request(), thread_id="t-journal")
        assert snapshot.journal
        for entry in snapshot.journal:
            assert entry.workflow_version == CONTENT_WORKFLOW_VERSION
            assert entry.input_hash.startswith("sha256:")
            assert entry.output_hash.startswith("sha256:")

    def test_skill_versions_written_into_run(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(_request(), thread_id="t-skills")
        assert dict(snapshot.skill_versions) == {
            "skill-brand-core": "1.2.0",
            "skill-medical-us": "2.0.0",
            "skill-market-us": "1.1.0",
            "skill-channel-linkedin": "1.0.0",
        }


class TestPauseResumeCancelRestart:
    def test_worker_restart_resumes_from_checkpoint(self) -> None:
        first = _workflow()
        snapshot = first.start(_request(), thread_id="t-restart")
        assert snapshot.status == "AWAITING_REVIEW"
        # 模拟 Worker 重启：同一 Checkpointer 上重建 Workflow 实例。
        second = ContentWorkflow(
            skills=SkillRegistry.from_fixture_file(SKILLS),
            retriever=_retriever(),
            model=FakeContentModel(),
            media_generator=FakeMediaGenerator(),
            checkpointer=first.checkpointer,
        )
        final = second.resume("t-restart", _approve())
        assert final.status == "APPROVED_PACKAGED"

    def test_cancel_blocks_resume_with_typed_error(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-cancel")
        cancelled = workflow.cancel("t-cancel")
        assert cancelled.status == "CANCELLED"
        with pytest.raises(WorkflowCancelledError):
            workflow.resume("t-cancel", _approve())

    def test_resume_without_pending_review_raises(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-done")
        workflow.resume("t-done", _approve())
        with pytest.raises(WorkflowStateError):
            workflow.resume("t-done", _approve())

    def test_start_twice_raises(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-dup")
        with pytest.raises(WorkflowStateError):
            workflow.start(_request(), thread_id="t-dup")

    def test_unknown_thread_raises(self) -> None:
        workflow = _workflow()
        with pytest.raises(WorkflowStateError):
            workflow.snapshot("t-missing")


class TestTargetedRework:
    def test_copy_issue_reruns_only_copy_and_compliance(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-copyfix")
        reworked = workflow.resume("t-copyfix", _reject("copy_issue"))
        assert reworked.status == "AWAITING_REVIEW"
        assert reworked.rework_count == 1
        counts = _node_counts(reworked)
        assert counts["generate_copy"] == 2
        assert counts["compliance_check"] == 2
        # 无关节点不得重跑。
        assert counts["retrieve_product_facts"] == 1
        assert counts["build_brief"] == 1
        assert counts["generate_media"] == 1
        final = workflow.resume("t-copyfix", _approve())
        assert final.status == "APPROVED_PACKAGED"

    def test_asset_issue_reruns_only_media_and_compliance(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-assetfix")
        reworked = workflow.resume("t-assetfix", _reject("asset_issue"))
        counts = _node_counts(reworked)
        assert counts["generate_media"] == 2
        assert counts["compliance_check"] == 2
        assert counts["generate_copy"] == 1
        assert counts["retrieve_product_facts"] == 1
        assert counts["build_brief"] == 1

    def test_fact_issue_reruns_full_downstream(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-factfix")
        reworked = workflow.resume("t-factfix", _reject("fact_issue"))
        counts = _node_counts(reworked)
        assert counts["retrieve_product_facts"] == 2
        assert counts["build_brief"] == 2
        assert counts["generate_copy"] == 2
        assert counts["generate_media"] == 2
        assert counts["compliance_check"] == 2
        assert counts["validate_input"] == 1

    def test_rejection_without_target_ends_rejected(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-reject")
        final = workflow.resume("t-reject", _reject(None))
        assert final.status == "REJECTED"
        assert final.package is None


class TestTypedFailuresAndBlocking:
    def test_uncited_claim_is_flagged_and_blocked(self) -> None:
        workflow = _workflow(FakeContentModel(mode="uncited_claim"))
        snapshot = workflow.start(_request(), thread_id="t-uncited")
        assert snapshot.status == "BLOCKED"
        assert snapshot.status_reason == "compliance_failed"
        assert snapshot.compliance is not None
        assert snapshot.compliance.uncited_claims
        rules = {v.rule for v in snapshot.compliance.violations}
        assert "claim_citation_required" in rules
        assert snapshot.package is None

    def test_invalid_model_output_fails_typed_not_faked(self) -> None:
        workflow = _workflow(FakeContentModel(mode="invalid_output"))
        with pytest.raises(InvalidNodeOutputError):
            workflow.start(_request(), thread_id="t-badmodel")

    def test_expired_skill_blocks_workflow(self) -> None:
        from content_workflow import SkillExpiredError

        workflow = _workflow()
        with pytest.raises(SkillExpiredError):
            workflow.start(
                _request(locale="de-DE"), thread_id="t-expired-skill"
            )

    def test_no_approved_facts_blocks_run(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(
            _request(product_ids=("product-unknown",)), thread_id="t-nofacts"
        )
        assert snapshot.status == "BLOCKED"
        assert snapshot.status_reason == "no_approved_facts"

    def test_wrong_request_id_in_decision_is_typed_failure(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="t-wrongid")
        with pytest.raises(InvalidNodeOutputError):
            workflow.resume("t-wrongid", _approve(request_id="req-9999"))


class TestDraftOnlyWithUnapprovedSkill:
    def test_draft_skill_allows_draft_but_never_approved_package(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(
            _request(channel="google_ads", objective="Alpha dosing"),
            thread_id="t-draft",
        )
        assert snapshot.status == "AWAITING_REVIEW"
        final = workflow.resume("t-draft", _approve())
        assert final.status == "DRAFT"
        assert final.status_reason == "skills_not_approved"
        assert final.package is None


class TestGoalCheck:
    def test_goal_passes_only_with_all_evidence(self) -> None:
        workflow = _workflow()
        pending = workflow.start(_request(), thread_id="t-goal")
        # 暂停在人工审核：缺 review_decision 证据 -> Goal 不通过。
        partial = check_goal(CONTENT_GOAL_SPEC, build_goal_evidence(pending))
        assert not partial.passed
        assert "review_decision" in partial.missing
        final = workflow.resume("t-goal", _approve())
        complete = check_goal(CONTENT_GOAL_SPEC, build_goal_evidence(final))
        assert complete.passed
