"""Reserved MIDEA Knowledge Base adapter (placeholder, not yet approved).

This module reserves the integration point only. The real MIDEA KB client
will implement ``KnowledgeBaseIndex`` behind a protected remote pipeline
once procurement/security approve the official API (endpoint, auth, data
retention, region). Until then:

* configuration defaults to ``enabled: false`` / ``mode: mock``;
* constructing the adapter in any non-mock mode without complete, approved
  configuration raises ``KnowledgeBaseNotConfiguredError`` — it never
  silently falls back to a fake success;
* no credential value ever appears here: only Secret Reference env names.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from product_rag.embedding import EmbeddingMetadata
from product_rag.errors import KnowledgeBaseNotConfiguredError
from product_rag.index import IndexEntry, RetrievalFilters, ScoredEntry


class MideaKnowledgeBaseConfig(BaseModel):
    """Shape of ``config/knowledge-base.yaml`` (secret references only)."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"]
    provider: Literal["midea_kb"]
    enabled: bool = False
    mode: Literal["mock", "sandbox", "live"] = "mock"
    endpoint_env: str = "MIDEA_KB_ENDPOINT"
    api_key_secret_ref_env: str = "MIDEA_KB_API_KEY_SECRET_REF"
    collection_env: str = "MIDEA_KB_COLLECTION"
    allowed_fqdns_env: str = "MIDEA_KB_ALLOWED_FQDNS"
    tls_verify: bool = True


class MideaKnowledgeBaseIndex:
    """Placeholder implementing the reserved ``KnowledgeBaseIndex`` surface.

    Every operation raises a typed error until the official MIDEA KB API is
    approved and the adapter is implemented in a protected pipeline.
    """

    def __init__(
        self,
        config: MideaKnowledgeBaseConfig,
        embedding: EmbeddingMetadata,
        *,
        resolved_settings: dict[str, str] | None = None,
    ) -> None:
        if not config.enabled or config.mode == "mock":
            raise KnowledgeBaseNotConfiguredError(
                "MIDEA Knowledge Base is not enabled; use the local index "
                "(mode: mock) until the official API is approved"
            )
        required = (
            config.endpoint_env,
            config.api_key_secret_ref_env,
            config.collection_env,
            config.allowed_fqdns_env,
        )
        settings = resolved_settings or {}
        missing = [name for name in required if not settings.get(name)]
        if missing:
            raise KnowledgeBaseNotConfiguredError(
                "MIDEA Knowledge Base configuration is incomplete; missing: "
                + ", ".join(sorted(missing))
            )
        raise KnowledgeBaseNotConfiguredError(
            "MIDEA Knowledge Base adapter is reserved but not implemented; "
            "real integration runs only in the protected remote pipeline"
        )

    @property
    def index_version(self) -> str:  # pragma: no cover - unreachable placeholder
        raise KnowledgeBaseNotConfiguredError("not implemented")

    @property
    def embedding_metadata(self) -> EmbeddingMetadata:  # pragma: no cover
        raise KnowledgeBaseNotConfiguredError("not implemented")

    def upsert(self, entries: list[IndexEntry]) -> None:  # pragma: no cover
        raise KnowledgeBaseNotConfiguredError("not implemented")

    def delete_by_source(
        self, source_id: str, *, tenant: str, source_version: str | None = None
    ) -> int:  # pragma: no cover
        raise KnowledgeBaseNotConfiguredError("not implemented")

    def query(
        self, vector: tuple[float, ...], filters: RetrievalFilters, k: int
    ) -> tuple[ScoredEntry, ...]:  # pragma: no cover
        raise KnowledgeBaseNotConfiguredError("not implemented")
