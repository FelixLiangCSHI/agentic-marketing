"""End-to-end: the Content Workflow media slot driven by the Jimeng
connector (mock transport). Proves the connector plugs into the existing
``GenerateMedia`` node via the ``MediaGenerator`` protocol without any
framework change, and that the asset lands in the generated object area.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from content_workflow import (
    ContentBriefV1,
    ContentWorkflow,
    FakeContentModel,
    InvalidNodeOutputError,
    SkillRegistry,
    WorkflowRequestV1,
)
from infra_core.clock import FakeClock
from infra_core.objectstore import FakeObjectStore
from infra_core.queue import FakeQueueClient, RetryPolicy
from jimeng_connector import (
    JimengConnector,
    JimengMediaGenerator,
    JimengMockTransport,
    NotSupportedError,
    load_config,
)
from product_rag import (
    FakeEmbeddingProvider,
    FakeProductAdapter,
    IngestionPipeline,
    InMemoryKnowledgeBaseIndex,
    Retriever,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "jimeng.yaml"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "jimeng"
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


def _brief() -> ContentBriefV1:
    return ContentBriefV1(
        request_id="req-0001",
        tenant=TENANT,
        market="US",
        locale="en-US",
        channel="linkedin",
        objective="Introduce Product Alpha dosing to physicians",
        target_audience=("physicians",),
        tone="professional",
        facts=(),
        banned_phrases=(),
        required_disclosures=(),
        max_headline_chars=150,
        skill_versions=(("brand", "v1"),),
    )


def _media_generator(
    scenario: str = "completed",
) -> tuple[JimengMediaGenerator, FakeObjectStore]:
    clock = FakeClock(datetime(2026, 8, 28, tzinfo=timezone.utc))
    object_store = FakeObjectStore(environment="local")
    connector = JimengConnector(
        load_config(CONFIG_PATH),
        env={},
        transport=JimengMockTransport(FIXTURES, scenario=scenario),  # type: ignore[arg-type]
        queue=FakeQueueClient(
            clock=clock,
            retry_policy=RetryPolicy(
                max_attempts=8,
                base_delay_seconds=1.0,
                max_delay_seconds=30.0,
                jitter_ratio=0.1,
            ),
            lease_seconds=60,
        ),
        object_store=object_store,
        environment="local",
        clock=clock,
    )
    generator = JimengMediaGenerator(
        connector, wait_fn=lambda: clock.advance(timedelta(seconds=120))
    )
    return generator, object_store


class TestWorkflowIntegration:
    def test_generate_media_slot_uses_jimeng_connector(self) -> None:
        generator, object_store = _media_generator()
        workflow = ContentWorkflow(
            skills=SkillRegistry.from_fixture_file(SKILLS),
            retriever=_retriever(),
            model=FakeContentModel(),
            media_generator=generator,
        )
        snapshot = workflow.start(_request(), thread_id="t-jimeng")
        assert snapshot.status == "AWAITING_REVIEW"
        assert snapshot.media is not None and len(snapshot.media) == 1
        asset = snapshot.media[0]
        assert asset.generator_id.startswith("jimeng:")
        assert asset.sha256.startswith("sha256:")
        assert asset.uri.startswith("objectstore://local/tenant-cshi/content-agent-generated/")
        # the binary actually landed in the generated area of the store
        assert any(
            "content-agent-generated" in key for key in object_store._objects  # noqa: SLF001
        )

    def test_failed_provider_job_is_typed_not_faked(self) -> None:
        generator, _ = _media_generator("failed_job")
        workflow = ContentWorkflow(
            skills=SkillRegistry.from_fixture_file(SKILLS),
            retriever=_retriever(),
            model=FakeContentModel(),
            media_generator=generator,
        )
        with pytest.raises(InvalidNodeOutputError, match="jimeng"):
            workflow.start(_request(), thread_id="t-jimeng-fail")

    def test_non_image_media_type_not_faked(self) -> None:
        generator, _ = _media_generator()
        brief_stub = None
        with pytest.raises(NotSupportedError):
            generator.generate_media(brief_stub, "video")  # type: ignore[arg-type]

    def test_rework_attempt_creates_new_job_but_same_attempt_is_idempotent(self) -> None:
        generator, _ = _media_generator()
        first = generator.generate_media(_brief(), "image", attempt=0)
        retry = generator.generate_media(_brief(), "image", attempt=0)
        rework = generator.generate_media(_brief(), "image", attempt=1)

        assert retry == first
        assert rework.asset_id != first.asset_id
        assert rework.sha256 != first.sha256
