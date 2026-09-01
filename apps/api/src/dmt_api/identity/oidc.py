"""OIDC-first enterprise identity provider.

Signature verification is delegated to an injected ``SignatureVerifier``
(JWKS-backed in DEV via the protected pipeline; a scripted fake in tests).
Everything else — issuer, audience, expiry, not-before, nonce, state — is
validated here, server-side. Role claims inside tokens are ignored: roles
come only from the controlled group mapping.

Without verifier material the provider refuses to authenticate
(``ProviderNotConfiguredError``); it never fakes success. Real DEV SSO
validation runs only in the protected pipeline and is BLOCKED until the
enterprise SSO app is delivered.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Protocol

from dmt_api.identity.provider import AuthenticationError, Principal
from dmt_api.identity.roles import Role, resolve_roles


class SignatureError(Exception):
    """The token signature could not be verified."""


class ProviderNotConfiguredError(Exception):
    """Enterprise SSO metadata/keys are not available in this environment."""


class SignatureVerifier(Protocol):
    """Verifies a compact token's signature and returns its claims."""

    def verify(self, token: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class OidcConfig:
    issuer: str
    audience: str
    group_claim: str = "groups"
    tenant_claim: str = "tenant"
    clock_skew_seconds: int = 30
    nonce_ttl_seconds: int = 300
    max_pending_nonces: int = 1024


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _numeric_date(claims: Mapping[str, Any], name: str) -> float | None:
    value = claims.get(name)
    if value is None:
        return None
    if type(value) not in (int, float):
        raise AuthenticationError(f"token {name} claim is malformed")
    numeric = float(value)
    if not isfinite(numeric):
        raise AuthenticationError(f"token {name} claim is malformed")
    return numeric


@dataclass(frozen=True, slots=True)
class _PendingNonce:
    nonce: str
    expires_at: datetime


@dataclass
class EnterpriseIdentityProvider:
    """OIDC ID-token validation with host-enforced structural checks."""

    config: OidcConfig
    signature_verifier: SignatureVerifier | None
    group_mapping: Mapping[str, frozenset[Role]]
    clock: Callable[[], datetime] = _utcnow
    _pending_nonces: dict[str, _PendingNonce] = field(default_factory=dict)

    def begin_login(self) -> tuple[str, str]:
        """Start an authorization-code login: returns (state, nonce)."""
        now = self.clock()
        self._evict_expired_nonces(now)
        if len(self._pending_nonces) >= self.config.max_pending_nonces:
            raise AuthenticationError("too many pending login attempts")
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        self._pending_nonces[state] = _PendingNonce(
            nonce=nonce,
            expires_at=now + timedelta(seconds=self.config.nonce_ttl_seconds),
        )
        return state, nonce

    def complete_login(self, *, state: str, id_token: str) -> Principal:
        """Finish a login: state is single-use and the nonce must match."""
        now = self.clock()
        self._evict_expired_nonces(now)
        pending = self._pending_nonces.pop(state, None)
        if pending is None:
            raise AuthenticationError("login state is unknown, expired, or already used")
        claims = self._verified_claims(id_token)
        if claims.get("nonce") != pending.nonce:
            raise AuthenticationError("nonce does not match the pending login")
        return self._principal_from_claims(claims)

    def authenticate(self, bearer_token: str) -> Principal:
        return self._principal_from_claims(self._verified_claims(bearer_token))

    def _verified_claims(self, token: str) -> Mapping[str, Any]:
        if self.signature_verifier is None:
            raise ProviderNotConfiguredError(
                "enterprise SSO is not configured in this environment (BLOCKED)"
            )
        try:
            claims = self.signature_verifier.verify(token)
        except SignatureError:
            raise AuthenticationError("token signature verification failed") from None
        self._validate_claims(claims)
        return claims

    def _evict_expired_nonces(self, now: datetime) -> None:
        expired = [
            state
            for state, pending in self._pending_nonces.items()
            if now >= pending.expires_at
        ]
        for state in expired:
            self._pending_nonces.pop(state, None)

    def _validate_claims(self, claims: Mapping[str, Any]) -> None:
        if claims.get("iss") != self.config.issuer:
            raise AuthenticationError("token issuer is not trusted")
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if self.config.audience not in audiences:
            raise AuthenticationError("token audience does not match this API")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthenticationError("token subject is missing")
        tenant = claims.get(self.config.tenant_claim)
        if not isinstance(tenant, str) or not re.fullmatch(
            r"^[a-z0-9][a-z0-9_-]{0,63}$", tenant
        ):
            raise AuthenticationError("token tenant claim is missing or malformed")
        now = self.clock().timestamp()
        skew = self.config.clock_skew_seconds
        exp = _numeric_date(claims, "exp")
        if exp is None or now > exp + skew:
            raise AuthenticationError("token is expired or has no expiry")
        nbf = _numeric_date(claims, "nbf")
        if nbf is not None and now < nbf - skew:
            raise AuthenticationError("token is not yet valid")
        iat = _numeric_date(claims, "iat")
        if iat is not None and iat > now + skew:
            raise AuthenticationError("token was issued in the future")

    def _principal_from_claims(self, claims: Mapping[str, Any]) -> Principal:
        raw_groups = claims.get(self.config.group_claim, [])
        groups = (
            tuple(str(group) for group in raw_groups)
            if isinstance(raw_groups, list)
            else ()
        )
        # Any 'roles' claim in the token is deliberately ignored.
        return Principal(
            subject=str(claims["sub"]),
            display_name=str(claims.get("name", claims["sub"])),
            tenant=str(claims[self.config.tenant_claim]),
            groups=groups,
            roles=resolve_roles(groups, self.group_mapping),
        )
