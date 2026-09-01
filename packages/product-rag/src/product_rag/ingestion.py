"""Ingestion pipeline: only approved, valid, hash-verified sources enter
the index; revocation events make entries unrecallable.

Every run produces an ``IngestionReport`` with counts, per-source results
and the cursor consumed, so ingestion is auditable and replayable.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

from product_rag.adapter import ProductAdapter
from product_rag.chunking import chunk_document
from product_rag.embedding import EmbeddingProvider
from product_rag.index import IndexEntry, KnowledgeBaseIndex
from product_rag.models import ProductDocumentV1


class SourceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_id: str
    source_version: str
    accepted: bool
    reason: str
    content_hash: str
    chunk_count: int


class IngestionReport(BaseModel):
    """Audit record of one ingestion run (no raw content, hashes only)."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tenant: str
    product_id: str
    market: str
    locale: str
    as_of: str
    index_version: str
    accepted_count: int
    rejected_count: int
    results: tuple[SourceResult, ...]


class ChangeReport(BaseModel):
    """Audit record of one change-feed application run."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    tenant: str
    cursor: str | None
    next_cursor: str | None
    revoked_sources: tuple[str, ...]
    deleted_entry_count: int


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class IngestionPipeline:
    """Wires ProductAdapter -> chunking -> embedding -> index."""

    def __init__(
        self,
        adapter: ProductAdapter,
        embedding_provider: EmbeddingProvider,
        index: KnowledgeBaseIndex,
    ) -> None:
        self._adapter = adapter
        self._embedding = embedding_provider
        self._index = index

    def ingest_product(
        self,
        product_id: str,
        market: str,
        locale: str,
        as_of: str,
        *,
        tenant: str,
    ) -> IngestionReport:
        """Ingest approved documents for one product/market/locale scope.

        The adapter already filters to APPROVED/effective/unexpired/
        unrevoked records; this pipeline re-verifies scope and content hash
        (defense in depth) and rejects—never silently drops—violations.
        """
        documents = self._adapter.list_approved_documents(
            product_id, market, locale, as_of, tenant=tenant
        )
        results: list[SourceResult] = []
        for document in documents:
            rejection = self._validate(document, product_id, market, locale, tenant)
            if rejection is not None:
                results.append(
                    SourceResult(
                        source_id=document.source_id,
                        source_version=document.source_version,
                        accepted=False,
                        reason=rejection,
                        content_hash=document.content_hash,
                        chunk_count=0,
                    )
                )
                continue
            chunks = chunk_document(document)
            vectors = self._embedding.embed_texts([chunk.text for chunk in chunks])
            entries = [
                IndexEntry(
                    chunk=chunk,
                    vector=vector,
                    embedding=self._embedding.metadata,
                    index_version=self._index.index_version,
                )
                for chunk, vector in zip(chunks, vectors)
            ]
            self._index.upsert(entries)
            results.append(
                SourceResult(
                    source_id=document.source_id,
                    source_version=document.source_version,
                    accepted=True,
                    reason="ok",
                    content_hash=document.content_hash,
                    chunk_count=len(entries),
                )
            )
        accepted = sum(1 for result in results if result.accepted)
        return IngestionReport(
            tenant=tenant,
            product_id=product_id,
            market=market,
            locale=locale,
            as_of=as_of,
            index_version=self._index.index_version,
            accepted_count=accepted,
            rejected_count=len(results) - accepted,
            results=tuple(results),
        )

    def apply_changes(self, cursor: str | None, *, tenant: str) -> ChangeReport:
        """Consume the change feed; REVOKED/DELETED purge index entries."""
        page = self._adapter.get_changes(cursor, tenant=tenant)
        revoked: list[str] = []
        deleted = 0
        for change in page.changes:
            if change.change_type in ("REVOKED", "DELETED"):
                deleted += self._index.delete_by_source(
                    change.entity_id,
                    tenant=tenant,
                    source_version=change.source_version,
                )
                revoked.append(change.entity_id)
        return ChangeReport(
            tenant=tenant,
            cursor=cursor,
            next_cursor=page.next_cursor,
            revoked_sources=tuple(revoked),
            deleted_entry_count=deleted,
        )

    def _validate(
        self,
        document: ProductDocumentV1,
        product_id: str,
        market: str,
        locale: str,
        tenant: str,
    ) -> str | None:
        if document.approval_status != "APPROVED":
            return f"approval_status={document.approval_status}"
        if document.revoked_at is not None:
            return "revoked"
        if (
            document.tenant != tenant
            or document.product_id != product_id
            or document.market != market
            or document.locale != locale
        ):
            return "scope_mismatch"
        if _sha256(document.content) != document.content_hash:
            return "content_hash_mismatch"
        return None
