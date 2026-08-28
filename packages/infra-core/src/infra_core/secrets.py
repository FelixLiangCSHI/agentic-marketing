"""Secret resolution: references in, opaque handles out.

Configuration may only carry ``secretref://provider/path`` references. The
resolver exchanges a reference for a :class:`SecretValue`, whose ``repr``
and ``str`` are masked so values cannot leak through logs, exceptions, or
serialization by accident. Values are never persisted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

SECRET_REF_PATTERN = re.compile(
    r"^secretref://(?P<provider>[a-z0-9][a-z0-9-]{0,63})/(?P<path>[A-Za-z0-9][A-Za-z0-9/_.-]{0,255})$"
)


class SecretError(Exception):
    """Base class for secret failures. Messages never carry secret values."""


class SecretRefFormatError(SecretError):
    """The string is not a valid secret reference (raw values rejected)."""


class SecretNotFoundError(SecretError):
    """No secret exists for the reference in this environment."""


@dataclass(frozen=True, slots=True)
class SecretRef:
    provider: str
    path: str

    @classmethod
    def parse(cls, raw: str) -> "SecretRef":
        match = SECRET_REF_PATTERN.match(raw)
        if match is None:
            raise SecretRefFormatError(
                "not a valid secretref:// reference; raw secret values are not allowed"
            )
        return cls(provider=match.group("provider"), path=match.group("path"))

    def render(self) -> str:
        return f"secretref://{self.provider}/{self.path}"


class SecretValue:
    """Opaque secret holder; only ``reveal()`` returns the value."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(****)"

    def __str__(self) -> str:
        return "****"

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)


class SecretResolver(Protocol):
    def resolve(self, ref: SecretRef) -> SecretValue: ...


@dataclass
class FakeSecretResolver:
    """In-memory resolver for tests/local dev; synthetic values only."""

    _store: dict[str, str] = field(default_factory=dict)

    def resolve(self, ref: SecretRef) -> SecretValue:
        raw = self._store.get(ref.render())
        if raw is None:
            raise SecretNotFoundError(
                f"no secret is registered for reference {ref.render()!r}"
            )
        return SecretValue(raw)
