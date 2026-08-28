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

import secrets
from math import isfinite
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    clock_skew_seconds: int = 30


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


@dataclass
class EnterpriseIdentityProvider:
    """OIDC ID-token validation with host-enforced structural checks."""

    config: OidcConfig
    signature_verifier: SignatureVerifier | None
    group_mapping: Mapping[str, frozenset[Role]]
    clock: Callable[[], datetime] = _utcnow
    _pending_nonces: dict[str, str] = field(default_factory=dict)

    def begin_login(self) -> tuple[str, str]:
        """Start an authorization-code login: returns (state, nonce)."""
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        self._pending_nonces[state] = nonce
        return state, nonce

    def complete_login(self, *, state: str, id_token: str) -> Principal:
        """Finish a login: state is single-use and the nonce must match."""
        nonce = self._pending_nonces.pop(state, None)
        if nonce is None:
            raise AuthenticationError("login state is unknown, expired, or already used")
        claims = self._verified_claims(id_token)
        if claims.get("nonce") != nonce:
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

    def _validate_claims(self, claims: Mapping[str, Any]) -> None:
        if claims.get("iss") != self.config.issuer:
            raise AuthenticationError("token issuer is not trusted")
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if self.config.audience not in audiences:
            raise AuthenticationError("token audience does not match this API")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthenticationError("token subject is missing")
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
        groups = tuple(str(group) for group in raw_groups) if isinstance(raw_groups, list) else ()
        # Any 'roles' claim in the token is deliberately ignored.
        return Principal(
            subject=str(claims["sub"]),
            display_name=str(claims.get("name", claims["sub"])),
            groups=groups,
            roles=resolve_roles(groups, self.group_mapping),
        )
