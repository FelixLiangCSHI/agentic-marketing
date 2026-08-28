"""Full-chain integration: Content Request -> RAG -> Brief -> Copy ->
Media -> Compliance -> Human Review -> Immutable Package.

Adversarial paths run on the same chain: reject + targeted rework before
approval, prompt-injection product text treated as data, and an uncited
claim that can never reach a package.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from builders import EXPIRES_AT, make_approval, make_versions

from content_workflow import (
    ContentWorkflow,
    FakeContentModel,
    FakeMediaGenerator,
    ReviewDecisionV1,
    SkillRegistry,
    WorkflowRequestV1,
    WorkflowSnapshot,
)
from content_workflow.contracts import model_hash
from product_rag import (
    FakeEmbeddingProvider,
    FakeProductAdapter,
    IngestionPipeline,
    InMemoryKnowledgeBaseIndex,
    Retriever,
)

from content_package import (
    ClaimBindingV1,
    NotApprovedError,
    PackageBuilder,
    PackageInputs,
    PackageStore,
    UncitedClaimError,
    canonical_content_hash,
    consumable,
    lineage_key,
)
from dmt_compliance import ComplianceEngine, DEFAULT_POLICY_PATH, load_policy

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "packages" / "content-workflow" / "fixtures" / "skills.json"
PRODUCT_FIXTURES = REPO_ROOT / "packages" / "product-rag" / "fixtures"
TENANT = "tenant-cshi"
AS_OF = "2026-06-01T00:00:00Z"
POLICY_AS_OF = "2026-06-01T00:00:00Z"

ENGINE = ComplianceEngine(load_policy(DEFAULT_POLICY_PATH))
BUILDER = PackageBuilder()


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


def _decision(outcome: str, target: str | None = None) -> ReviewDecisionV1:
    return ReviewDecisionV1.model_validate(
        {
            "request_id": "req-0001",
            "reviewer_id": "emp-reviewer",
            "outcome": outcome,
            "rework_target": target,
            "notes": "e2e",
        }
    )


def _package_inputs(snapshot: WorkflowSnapshot) -> PackageInputs:
    assert snapshot.brief is not None and snapshot.copy_draft is not None
    draft = snapshot.copy_draft
    media = tuple(snapshot.media or ())
    versions = make_versions(
        skill_versions=tuple(snapshot.skill_versions),
        model_id=draft.model_id,
    )
    channel_variants = ((draft.channel, (f"cv-{draft.request_id}",)),)
    compliance_result = ENGINE.evaluate(
        brief=snapshot.brief,
        draft=draft,
        media=media,
        requested_media_types=snapshot.request.requested_media_types,
        as_of=POLICY_AS_OF,
    )
    claims = tuple(
        ClaimBindingV1(
            text=claim.text,
            source_id=claim.citation.source_id,
            source_version=claim.citation.source_version,
            source_excerpt_hash=claim.citation.chunk_hash,
            expires_at=claim.citation.expires_at,
        )
        for claim in draft.claims
        if claim.citation is not None
    )
    content_hash = canonical_content_hash(
        copy_hash=model_hash(draft),
        claims=claims,
        asset_hashes=tuple(asset.sha256 for asset in media),
        versions=versions,
        channel_variants=channel_variants,
    )
    return PackageInputs(
        product_id="product-alpha",
        market=snapshot.request.market,
        locale=snapshot.request.locale,
        target_audience=tuple(snapshot.request.target_audience),
        draft=draft,
        media=media,
        asset_uris=tuple(asset.uri for asset in media),
        requested_channels=(snapshot.request.channel,),
        channel_variants=channel_variants,
        compliance_result=compliance_result,
        approvals=(
            make_approval("medical", artifact_hash=content_hash),
            make_approval("marketing", artifact_hash=content_hash),
        ),
        versions=versions,
        expires_at=EXPIRES_AT,
    )


class TestFullChain:
    def test_request_to_immutable_package(self) -> None:
        workflow = _workflow()
        snapshot = workflow.start(_request(), thread_id="e2e-happy")
        assert snapshot.status == "AWAITING_REVIEW"
        approved = workflow.resume("e2e-happy", _decision("approved"))
        assert approved.status == "APPROVED_PACKAGED"
        assert approved.package is not None

        inputs = _package_inputs(approved)
        package = BUILDER.build(inputs, as_of=AS_OF)
        assert package.status == "APPROVED"
        assert package.claims  # 100% cited claims
        assert all(
            claim.source_excerpt_hash.startswith("sha256:")
            for claim in package.claims
        )
        store = PackageStore()
        store.publish(package, recorded_at=AS_OF)
        active = store.active(lineage_key(package))
        assert active is not None
        assert consumable(
            package, as_of=AS_OF, ledger_status=active.status
        ) == (True, "consumable")

    def test_reject_rework_then_approve_then_package(self) -> None:
        workflow = _workflow()
        workflow.start(_request(), thread_id="e2e-rework")
        reworked = workflow.resume(
            "e2e-rework", _decision("rejected", "copy_issue")
        )
        assert reworked.status == "AWAITING_REVIEW"
        approved = workflow.resume("e2e-rework", _decision("approved"))
        assert approved.status == "APPROVED_PACKAGED"
        package = BUILDER.build(_package_inputs(approved), as_of=AS_OF)
        assert package.status == "APPROVED"

    def test_uncited_claim_chain_never_reaches_package(self) -> None:
        workflow = _workflow(FakeContentModel(mode="uncited_claim"))
        snapshot = workflow.start(_request(), thread_id="e2e-uncited")
        # 工作流内联合规门已 BLOCK；引擎与 Builder 双重拒绝。
        assert snapshot.status == "BLOCKED"
        assert snapshot.copy_draft is not None
        inputs = _package_inputs(snapshot)
        assert inputs.compliance_result.automated_status == "BLOCKED"
        with pytest.raises((NotApprovedError, UncitedClaimError)):
            BUILDER.build(inputs, as_of=AS_OF)

    def test_prompt_injection_text_is_treated_as_data(self) -> None:
        # Product fixture 含注入文本；确定性链路不执行它，包内容保持受控。
        workflow = _workflow()
        snapshot = workflow.start(_request(), thread_id="e2e-injection")
        approved = workflow.resume("e2e-injection", _decision("approved"))
        package = BUILDER.build(_package_inputs(approved), as_of=AS_OF)
        for claim in package.claims:
            assert "ignore previous" not in claim.text.lower()
        assert approved.copy_draft is not None
        assert "ignore previous" not in " ".join(
            approved.copy_draft.body.lower().split()
        )
