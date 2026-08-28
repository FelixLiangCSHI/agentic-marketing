"""Isolated memory: stable preferences only.

Namespaced by agent / user / brand / market. One namespace can never read
another's entries. Only allowlisted preference keys with small scalar values
are accepted — no run state, transcripts, or derived facts (ADR-005).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from harness_core.errors import MemoryPolicyError
from harness_core.tools import AgentType

_MAX_VALUE_BYTES = 512

Scalar = str | int | float | bool


@dataclass(frozen=True, slots=True)
class MemoryNamespace:
    agent_type: AgentType
    user_id: str
    brand: str
    market: str


class MemoryStore:
    def __init__(self, *, allowed_keys: frozenset[str]) -> None:
        self._allowed_keys = allowed_keys
        self._entries: dict[tuple[MemoryNamespace, str], Scalar] = {}

    def put(self, namespace: MemoryNamespace, key: str, value: Scalar) -> None:
        if key not in self._allowed_keys:
            raise MemoryPolicyError(
                f"memory key {key!r} is not an allowlisted stable preference"
            )
        if not isinstance(value, (str, int, float, bool)):
            raise MemoryPolicyError("memory values must be small scalars")
        if len(json.dumps(value).encode("utf-8")) > _MAX_VALUE_BYTES:
            raise MemoryPolicyError("memory value exceeds the stable-preference size limit")
        self._entries[(namespace, key)] = value

    def get(self, namespace: MemoryNamespace, key: str) -> Scalar | None:
        return self._entries.get((namespace, key))
