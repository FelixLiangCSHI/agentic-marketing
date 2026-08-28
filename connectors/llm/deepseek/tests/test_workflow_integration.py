"""Content Workflow end-to-end with the DeepSeek mock connector.

Proves the ``BuildBrief/GenerateCopy`` model slot can switch from the fake
model to the DeepSeek connector (mock mode) without changing the graph:
grounded output packages after human approval; an uncited claim is
flagged and BLOCKED; invalid model JSON is a typed node failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from content_workflow import (
    ContentWorkflow,
    FakeMediaGenerator,
    InvalidNodeOutputError,
    ReviewDecisionV1,
    SkillRegistry,
    WorkflowRequestV1,
)
from deepseek_connector import (
    DeepSeekConnector,
    DeepSeekContentModel,
    DeepSeekMockTransport,
    load_config,
)
from deepseek_connector.transport import MockScenario
from product_rag import (
    FakeEmbeddingProvider,
    FakeProductAdapter,
    IngestionPipeline,
    InMemoryKnowledgeBaseIndex,
    Retriever,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = REPO_ROOT / "config" / "deepseek.yaml"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "deepseek"
SKILLS = REPO_ROOT / "packages" / "content-workflow" / "fixtures" / "skills.json"
PRODUCT_FIXTURES = REPO_ROOT / "packages" / "product-rag" / "fixtures"
TENANT = "tenant-cshi"
AS_OF = "2026-06-01T00:00:00Z"


def _retriever() -> Retriever:
    embedding = FakeEmbeddingProvider()
    adapter = FakeProductAdapter.from_fixture_dir(PRODUCT_FIXTURES)
    index = InMemoryKnowledgeBaseIndex(embedding.metadata)
    pipeline = IngestionPipeline(adapter, embedding, index)
    pipeline.ingest_product("product-alpha", "US", "en-US", AS_OF, tenant=TENANT)
    return Retriever(index, embedding)


def _model(scenario: MockScenario) -> DeepSeekContentModel:
    connector = DeepSeekConnector(
        load_config(CONFIG_PATH),
        env={},
        transport=DeepSeekMockTransport(FIXTURES, scenario=scenario),
    )
    return DeepSeekContentModel(connector)


def _workflow(scenario: MockScenario) -> ContentWorkflow:
    return ContentWorkflow(
        skills=SkillRegistry.from_fixture_file(SKILLS),
        retriever=_retriever(),
        model=_model(scenario),
        media_generator=FakeMediaGenerator(),
    )


def _request() -> WorkflowRequestV1:
    return WorkflowRequestV1.model_validate(
        {
            "request_id": "req-ds-01",
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


class TestWorkflowWithDeepSeekMock:
    def test_grounded_mock_reaches_review_and_packages(self) -> None:
        workflow = _workflow("normal")
        snapshot = workflow.start(_request(), thread_id="t-ds-happy")
        assert snapshot.status == "AWAITING_REVIEW"
        assert snapshot.copy_draft is not None
        assert snapshot.copy_draft.model_id.startswith("deepseek:")
        assert all(claim.citation is not None for claim in snapshot.copy_draft.claims)
        decision = ReviewDecisionV1(
            request_id="req-ds-01",
            reviewer_id="emp-reviewer",
            outcome="approved",
            rework_target=None,
            notes="fixture-approved",
        )
        done = workflow.resume("t-ds-happy", decision)
        assert done.status == "APPROVED_PACKAGED"
        assert done.package is not None

    def test_uncited_claim_from_model_is_blocked(self) -> None:
        workflow = _workflow("uncited_claim")
        snapshot = workflow.start(_request(), thread_id="t-ds-uncited")
        assert snapshot.status == "BLOCKED"

    def test_invalid_model_json_is_typed_failure(self) -> None:
        workflow = _workflow("invalid_json")
        with pytest.raises(InvalidNodeOutputError):
            workflow.start(_request(), thread_id="t-ds-invalid")

    def test_model_supplied_citations_are_ignored_unknown_hash_uncited(self) -> None:
        # 模型编造 chunk_hash 时不得命中引用：适配层只信 RAG 提供的事实。
        model = _model("normal")
        from content_workflow.contracts import ContentBriefV1

        brief = _workflow("normal")  # build a real brief via a started run
        snapshot = brief.start(_request(), thread_id="t-ds-cite")
        assert snapshot.brief is not None
        parsed = model._parse_draft(  # noqa: SLF001 - targeted unit assertion
            snapshot.brief,
            '{"headline": "H", "body": "B", '
            '"claims": [{"text": "made up", "chunk_hash": "sha256:' + "f" * 64 + '"}]}',
        )
        assert parsed.claims[0].citation is None
