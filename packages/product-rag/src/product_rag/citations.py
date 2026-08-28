"""Citation model: the only sanctioned way to reference product facts.

Citations are constructed exclusively by the index/retrieval layer from
ingested, approved chunks. Models never generate or mutate citations.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from product_rag.models import (
    DateTimeUtc,
    Identifier,
    Locale,
    Market,
    SemVer,
    Sha256Hash,
)


class Citation(BaseModel):
    """Verifiable pointer into an approved source document version."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_id: Identifier
    source_version: SemVer
    product_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    char_start: int
    char_end: int
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    source_content_hash: Sha256Hash
    chunk_hash: Sha256Hash
