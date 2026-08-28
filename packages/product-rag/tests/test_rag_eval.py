"""Golden-query Recall@k eval for the fake-embedding RAG pipeline.

Dataset: rag-golden-queries v1 (inline below, bound to the synthetic
fixtures in ``fixtures/``). Hard gate P2-CP01: Recall@5 >= 0.95 on the
golden set. Golden answers are versioned — never edit answers to chase
recall; fix chunking/embedding/retrieval instead.

This eval runs in the product-rag CI job (the top-level eval job installs
only harness-core). It validates pipeline mechanics with the deterministic
fake embedding; real-embedding quality acceptance stays BLOCKED (B-03).
"""

from __future__ import annotations

from pathlib import Path

from product_rag import (
    FakeEmbeddingProvider,
    FakeProductAdapter,
    IngestionPipeline,
    InMemoryKnowledgeBaseIndex,
    RetrievalFilters,
    Retriever,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
TENANT = "tenant-cshi"
AS_OF = "2026-06-01T00:00:00Z"
K = 5
RECALL_THRESHOLD = 0.95

GOLDEN_DATASET_VERSION = "rag-golden-queries-v1"
# (query, market, locale, expected source_id)
GOLDEN_QUERIES: tuple[tuple[str, str, str, str], ...] = (
    ("indicated for adult patients condition X", "US", "en-US", "doc-alpha-label"),
    ("what is the indication of product alpha", "US", "en-US", "doc-alpha-label"),
    ("10mg once daily dosing", "US", "en-US", "doc-alpha-dosing"),
    ("dosing information for product alpha", "US", "en-US", "doc-alpha-dosing"),
    ("produktinformation product alpha", "US", "de-DE", "doc-alpha-de"),
    ("cn market approved overview", "CN", "zh-CN", "doc-alpha-cn"),
)


def test_golden_recall_at_k_meets_threshold() -> None:
    embedding = FakeEmbeddingProvider()
    adapter = FakeProductAdapter.from_fixture_dir(FIXTURE_DIR)
    index = InMemoryKnowledgeBaseIndex(embedding.metadata)
    pipeline = IngestionPipeline(adapter, embedding, index)
    for market, locale in (("US", "en-US"), ("US", "de-DE"), ("CN", "zh-CN")):
        pipeline.ingest_product("product-alpha", market, locale, AS_OF, tenant=TENANT)
    retriever = Retriever(index, embedding)

    hits = 0
    misses: list[str] = []
    for query, market, locale, expected_source in GOLDEN_QUERIES:
        filters = RetrievalFilters(
            tenant=TENANT,
            product_id="product-alpha",
            market=market,  # type: ignore[arg-type]
            locale=locale,
            as_of=AS_OF,
        )
        passages = retriever.retrieve(query, filters, k=K)
        if any(p.citation.source_id == expected_source for p in passages):
            hits += 1
        else:
            misses.append(query)
    recall = hits / len(GOLDEN_QUERIES)
    assert recall >= RECALL_THRESHOLD, (
        f"Recall@{K}={recall:.2f} below {RECALL_THRESHOLD} on "
        f"{GOLDEN_DATASET_VERSION}; misses: {misses}"
    )
