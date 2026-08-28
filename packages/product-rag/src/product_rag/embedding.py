"""Embedding provider boundary.

Only deterministic fake embeddings exist in the repository. Real provider
adapters run exclusively in protected remote pipelines (Phase 01 B-03 /
B-06 gates); they must implement the same protocol and record identical
metadata. Every vector is bound to provider/model/deployment/dimension so
indexes can never silently mix embedding spaces.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class EmbeddingMetadata(BaseModel):
    """Identity of the embedding space; part of every index version."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    provider: str
    model: str
    deployment: str
    dimension: int


class EmbeddingProvider(Protocol):
    """Read-only embedding boundary; implementations must be deterministic
    for identical input within one (provider, model, deployment)."""

    @property
    def metadata(self) -> EmbeddingMetadata:
        ...

    def embed_texts(self, texts: list[str]) -> list[tuple[float, ...]]:
        ...


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class FakeEmbeddingProvider:
    """Deterministic feature-hashing bag-of-words embedding.

    Token overlap between query and chunk produces meaningful similarity,
    which lets golden Recall@k evals run without any real model. Never a
    substitute for real embedding quality acceptance (kept BLOCKED).
    """

    def __init__(self, *, dimension: int = 256, deployment: str = "local") -> None:
        self._metadata = EmbeddingMetadata(
            provider="fake",
            model="feature-hash-bow-v1",
            deployment=deployment,
            dimension=dimension,
        )

    @property
    def metadata(self) -> EmbeddingMetadata:
        return self._metadata

    def embed_texts(self, texts: list[str]) -> list[tuple[float, ...]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> tuple[float, ...]:
        dimension = self._metadata.dimension
        vector = [0.0] * dimension
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[slot] += sign
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(component / norm for component in vector)
