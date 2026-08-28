"""Versioned knowledge-base index boundary.

``KnowledgeBaseIndex`` is the reserved integration interface: the local
``InMemoryKnowledgeBaseIndex`` implements it for repo/CI, and the future
MIDEA Knowledge Base adapter (see ``midea.py``) must implement the same
protocol behind a protected remote pipeline. Agents and workflows depend
only on this protocol, never on a concrete backend.

Rules enforced here:
* an index is bound to exactly one embedding space (provider/model/
  deployment/dimension) and one index version — mixing raises a typed error;
* queries require the full tenant/product/market/locale/as_of filter set;
* deletions (revocations) make entries unrecallable immediately.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from product_rag.chunking import Chunk
from product_rag.embedding import EmbeddingMetadata
from product_rag.errors import IndexVersionMismatchError, MissingRetrievalFilterError
from product_rag.models import DateTimeUtc, Identifier, Locale, Market


class IndexEntry(BaseModel):
    """A chunk plus its vector, bound to one embedding space."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    chunk: Chunk
    vector: tuple[float, ...]
    embedding: EmbeddingMetadata
    index_version: str


class RetrievalFilters(BaseModel):
    """Mandatory query scope; every field is required by construction."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tenant: Identifier
    product_id: Identifier
    market: Market
    locale: Locale
    as_of: DateTimeUtc


class ScoredEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    entry: IndexEntry
    score: float


class KnowledgeBaseIndex(Protocol):
    """Reserved interface for pluggable knowledge bases (local or MIDEA KB)."""

    @property
    def index_version(self) -> str:
        ...

    @property
    def embedding_metadata(self) -> EmbeddingMetadata:
        ...

    def upsert(self, entries: list[IndexEntry]) -> None:
        ...

    def delete_by_source(
        self, source_id: str, source_version: str | None = None
    ) -> int:
        ...

    def query(
        self, vector: tuple[float, ...], filters: RetrievalFilters, k: int
    ) -> tuple[ScoredEntry, ...]:
        ...


def make_index_version(embedding: EmbeddingMetadata, *, generation: int = 1) -> str:
    """Index version derives from the embedding space; model upgrades or
    rebuilds produce a new version instead of mutating an existing index."""
    return (
        f"{embedding.provider}_{embedding.model}_{embedding.deployment}_"
        f"d{embedding.dimension}_g{generation}"
    ).replace(".", "-")


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


class InMemoryKnowledgeBaseIndex:
    """Deterministic local implementation for repo/CI and unit evals."""

    def __init__(self, embedding: EmbeddingMetadata, *, generation: int = 1) -> None:
        self._embedding = embedding
        self._index_version = make_index_version(embedding, generation=generation)
        self._entries: dict[str, IndexEntry] = {}

    @property
    def index_version(self) -> str:
        return self._index_version

    @property
    def embedding_metadata(self) -> EmbeddingMetadata:
        return self._embedding

    def upsert(self, entries: list[IndexEntry]) -> None:
        for entry in entries:
            if entry.embedding != self._embedding:
                raise IndexVersionMismatchError(
                    "entry embedding space does not match this index; "
                    "model upgrades require a new index version"
                )
            if entry.index_version != self._index_version:
                raise IndexVersionMismatchError(
                    f"entry index version {entry.index_version!r} does not match "
                    f"index {self._index_version!r}"
                )
            if len(entry.vector) != self._embedding.dimension:
                raise IndexVersionMismatchError(
                    "vector dimension does not match the embedding space"
                )
        for entry in entries:
            self._entries[entry.chunk.chunk_id] = entry

    def delete_by_source(
        self, source_id: str, source_version: str | None = None
    ) -> int:
        doomed = [
            chunk_id
            for chunk_id, entry in self._entries.items()
            if entry.chunk.source_id == source_id
            and (source_version is None or entry.chunk.source_version == source_version)
        ]
        for chunk_id in doomed:
            del self._entries[chunk_id]
        return len(doomed)

    def query(
        self, vector: tuple[float, ...], filters: RetrievalFilters, k: int
    ) -> tuple[ScoredEntry, ...]:
        if k < 1:
            raise MissingRetrievalFilterError("k must be >= 1")
        candidates = [
            entry
            for entry in self._entries.values()
            if entry.chunk.tenant == filters.tenant
            and entry.chunk.product_id == filters.product_id
            and entry.chunk.market == filters.market
            and entry.chunk.locale == filters.locale
            and entry.chunk.effective_from <= filters.as_of
            and (entry.chunk.expires_at is None or entry.chunk.expires_at > filters.as_of)
        ]
        scored = sorted(
            (ScoredEntry(entry=entry, score=_dot(vector, entry.vector))
             for entry in candidates),
            key=lambda s: (-s.score, s.entry.chunk.chunk_id),
        )
        return tuple(scored[:k])
