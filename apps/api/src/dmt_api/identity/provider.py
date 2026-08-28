"""Identity providers.

``FakeIdentityProvider`` backs local development and normal PR CI. It issues
opaque, single-provider session tokens; the caller can never influence its
own roles — those are resolved server-side from the group mapping.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from dmt_api.identity.roles import Role, resolve_roles


class AuthenticationError(Exception):
    """The presented credential is missing, invalid, expired, or revoked.

    Messages must never echo the credential itself.
    """


@dataclass(frozen=True, slots=True)
class Principal:
    """A server-side verified identity."""

    subject: str
    display_name: str
    groups: tuple[str, ...]
    roles: frozenset[Role]


class IdentityProvider(Protocol):
    """Turns a bearer credential into a verified :class:`Principal`."""

    def authenticate(self, bearer_token: str) -> Principal: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class _FakeSession:
    subject: str
    display_name: str
    groups: tuple[str, ...]
    expires_at: datetime


@dataclass
class FakeIdentityProvider:
    """In-memory identity provider for local/PR use only.

    Sessions are opaque random tokens; identity attributes live server-side.
    Never used outside ``mode: mock`` environments.
    """

    group_mapping: Mapping[str, frozenset[Role]]
    clock: Callable[[], datetime] = _utcnow
    _sessions: dict[str, _FakeSession] = field(default_factory=dict)

    def issue_session(
        self,
        subject: str,
        display_name: str,
        *,
        groups: tuple[str, ...] = (),
        ttl: timedelta = timedelta(hours=8),
    ) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = _FakeSession(
            subject=subject,
            display_name=display_name,
            groups=groups,
            expires_at=self.clock() + ttl,
        )
        return token

    def revoke_session(self, token: str) -> None:
        self._sessions.pop(token, None)

    def advance_clock(self, clock: Callable[[], datetime]) -> None:
        """Test hook: replace the clock (e.g. to simulate expiry)."""
        self.clock = clock

    def authenticate(self, bearer_token: str) -> Principal:
        session = self._sessions.get(bearer_token)
        if session is None:
            raise AuthenticationError("session is unknown or has been revoked")
        if self.clock() >= session.expires_at:
            self._sessions.pop(bearer_token, None)
            raise AuthenticationError("session has expired")
        return Principal(
            subject=session.subject,
            display_name=session.display_name,
            groups=session.groups,
            roles=resolve_roles(session.groups, self.group_mapping),
        )
