"""Application settings.

Secrets are never stored here: only secret *references* are allowed in
configuration. In Phase 01 every external capability stays in ``mode: mock``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_ALLOWED_MODES = frozenset({"mock"})
_ALLOWED_ENVIRONMENTS = frozenset({"local", "dev", "sit", "uat", "prd"})


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the process environment."""

    mode: str = "mock"
    environment: str = "local"
    problems: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.environ.get("DMT_MODE", "mock")
        environment = os.environ.get("DMT_ENVIRONMENT", "local")
        problems: list[str] = []
        if mode not in _ALLOWED_MODES:
            problems.append(
                f"DMT_MODE={mode!r} is not allowed in Phase 01; only 'mock' is permitted"
            )
        if environment not in _ALLOWED_ENVIRONMENTS:
            problems.append(f"DMT_ENVIRONMENT={environment!r} is not a known environment")
        return cls(mode=mode, environment=environment, problems=tuple(problems))

    @property
    def is_ready(self) -> bool:
        return not self.problems
