"""Application settings.

Secrets are never stored here: only secret *references* are allowed in
configuration. In Phase 01 every external capability stays in ``mode: mock``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_ALLOWED_MODES = frozenset({"mock"})
_ALLOWED_ENVIRONMENTS = frozenset({"local", "dev", "sit", "uat", "prd"})


def _int_from_env(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
    problems: list[str],
) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        problems.append(f"{name} must be an integer")
        return default
    if not minimum <= value <= maximum:
        problems.append(f"{name} must be between {minimum} and {maximum}")
        return default
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the process environment."""

    mode: str = "mock"
    environment: str = "local"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    request_max_body_bytes: int = 1_048_576
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
        database_pool_size = _int_from_env(
            "DMT_DATABASE_POOL_SIZE", 5, minimum=1, maximum=100, problems=problems
        )
        database_max_overflow = _int_from_env(
            "DMT_DATABASE_MAX_OVERFLOW", 10, minimum=0, maximum=100, problems=problems
        )
        database_pool_timeout_seconds = _int_from_env(
            "DMT_DATABASE_POOL_TIMEOUT_SECONDS",
            30,
            minimum=1,
            maximum=300,
            problems=problems,
        )
        request_max_body_bytes = _int_from_env(
            "DMT_REQUEST_MAX_BODY_BYTES",
            1_048_576,
            minimum=1024,
            maximum=104_857_600,
            problems=problems,
        )
        return cls(
            mode=mode,
            environment=environment,
            database_pool_size=database_pool_size,
            database_max_overflow=database_max_overflow,
            database_pool_timeout_seconds=database_pool_timeout_seconds,
            request_max_body_bytes=request_max_body_bytes,
            problems=tuple(problems),
        )

    @property
    def is_ready(self) -> bool:
        return not self.problems
