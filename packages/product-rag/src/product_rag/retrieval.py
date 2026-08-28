"""Retrieval over the versioned knowledge-base index.

Every returned passage carries a verifiable ``Citation`` built exclusively
from index entries — models never generate citations. All filters are
mandatory by construction (``RetrievalFilters``); the query text itself is
untrusted data and cannot widen the scope.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from product_rag.citations import Citation
from product_rag.embedding import EmbeddingProvider
from product_rag.index import KnowledgeBaseIndex, RetrievalFilters


class RetrievedPassage(BaseModel):
    """Approved text fragment plus its verifiable citation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str
    score: float
    citation: Citation
    index_version: str


class Retriever:
    def __init__(
        self, index: KnowledgeBaseIndex, embedding_provider: EmbeddingProvider
    ) -> None:
        if index.embedding_metadata != embedding_provider.metadata:
            # 查询向量与索引向量必须来自同一嵌入空间。
            from product_rag.errors import IndexVersionMismatchError

            raise IndexVersionMismatchError(
                "retriever embedding provider does not match the index "
                "embedding space"
            )
        self._index = index
        self._embedding = embedding_provider

    def retrieve(
        self, query: str, filters: RetrievalFilters, *, k: int = 5
    ) -> tuple[RetrievedPassage, ...]:
        vector = self._embedding.embed_texts([query])[0]
        scored = self._index.query(vector, filters, k)
        passages: list[RetrievedPassage] = []
        for item in scored:
            chunk = item.entry.chunk
            passages.append(
                RetrievedPassage(
                    text=chunk.text,
                    score=item.score,
                    citation=Citation(
                        source_id=chunk.source_id,
                        source_version=chunk.source_version,
                        product_id=chunk.product_id,
                        tenant=chunk.tenant,
                        market=chunk.market,
                        locale=chunk.locale,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        effective_from=chunk.effective_from,
                        expires_at=chunk.expires_at,
                        source_content_hash=chunk.source_content_hash,
                        chunk_hash=chunk.chunk_hash,
                    ),
                    index_version=item.entry.index_version,
                )
            )
        return tuple(passages)
