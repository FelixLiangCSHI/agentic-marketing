"""Minimal context: large results travel as URI + hash + summary only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Reference to a large artifact; the payload itself never enters context."""

    uri: str
    sha256: str
    summary: str


class ArtifactStore(Protocol):
    def put(self, payload: bytes) -> str:
        """Store the payload and return its URI."""
        ...


@dataclass
class InMemoryArtifactStore:
    """Local fake store; Phase 01 never touches a real object store."""

    payloads: dict[str, bytes] | None = None

    def __post_init__(self) -> None:
        if self.payloads is None:
            self.payloads = {}

    def put(self, payload: bytes) -> str:
        assert self.payloads is not None
        uri = f"memory://artifacts/{len(self.payloads)}"
        self.payloads[uri] = payload
        return uri


class ContextPacker:
    """Keeps model context minimal.

    Values within ``max_inline_bytes`` pass through; anything larger is
    stored and replaced by an :class:`ArtifactRef` (URI + sha256 + summary).
    """

    def __init__(self, store: ArtifactStore, *, max_inline_bytes: int = 2048) -> None:
        self._store = store
        self._max_inline_bytes = max_inline_bytes

    def pack(self, value: Any, *, summary: str) -> Any | ArtifactRef:
        encoded = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
        if len(encoded) <= self._max_inline_bytes:
            return value
        uri = self._store.put(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        return ArtifactRef(uri=uri, sha256=f"sha256:{digest}", summary=summary)
