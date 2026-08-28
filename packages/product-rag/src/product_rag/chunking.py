"""Deterministic chunking of approved product documents.

Every chunk carries its source document version, exact character range,
market, locale and validity window so downstream citations are verifiable
byte-for-byte against the approved source.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

from product_rag.models import (
    DateTimeUtc,
    Identifier,
    Locale,
    Market,
    ProductDocumentV1,
    SemVer,
    Sha256Hash,
)

DEFAULT_MAX_CHUNK_CHARS = 400


class Chunk(BaseModel):
    """Chunk of an approved document; free text remains untrusted data."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    chunk_id: Identifier
    source_id: Identifier
    source_version: SemVer
    product_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    char_start: int
    char_end: int
    text: str
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    source_content_hash: Sha256Hash
    chunk_hash: Sha256Hash


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_document(
    document: ProductDocumentV1,
    *,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> tuple[Chunk, ...]:
    """Split a document into deterministic, position-preserving chunks.

    Splits on sentence boundaries where possible; every chunk's
    ``[char_start, char_end)`` range reproduces its text exactly from the
    source document content.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    text = document.content
    spans: list[tuple[int, int]] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            # 优先在句号/换行边界断开，保持确定性。
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind("\n"), window.rfind("。"))
            if cut > 0:
                end = start + cut + 1
        spans.append((start, end))
        start = end
    chunks: list[Chunk] = []
    for ordinal, (char_start, char_end) in enumerate(spans):
        chunk_text = text[char_start:char_end]
        chunks.append(
            Chunk(
                chunk_id=(
                    f"{document.source_id}_v"
                    f"{document.source_version.replace('.', '-')}_c{ordinal}"
                ),
                source_id=document.source_id,
                source_version=document.source_version,
                product_id=document.product_id,
                tenant=document.tenant,
                market=document.market,
                locale=document.locale,
                char_start=char_start,
                char_end=char_end,
                text=chunk_text,
                effective_from=document.effective_from,
                expires_at=document.expires_at,
                source_content_hash=document.content_hash,
                chunk_hash=_sha256(chunk_text),
            )
        )
    return tuple(chunks)
