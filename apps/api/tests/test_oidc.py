"""Security tests for the OIDC-first EnterpriseIdentityProvider.

The signature verifier is injected; tests use a scripted fake so no real
crypto material or vendor endpoint is needed. Every structural check
(issuer, audience, expiry, nonce, state) is host-enforced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pytest

from dmt_api.identity.oidc import (
    EnterpriseIdentityProvider,
    OidcConfig,
    ProviderNotConfiguredError,
    SignatureError,
)
from dmt_api.identity.provider import AuthenticationError
from dmt_api.identity.roles import Role

_NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)

CONFIG = OidcConfig(
    issuer="https://sso.corp.example/realms/dmt",
    audience="dmt-portal",
)

GROUP_MAPPING: dict[str, frozenset[Role]] = {
    "grp-content": frozenset({Role.CONTENT_CREATOR}),
}


class ScriptedVerifier:
    """Fake signature verifier: only tokens in the script are 'signed'."""

    def __init__(self, tokens: Mapping[str, Mapping[str, Any]]) -> None:
        self._tokens = dict(tokens)

    def add(self, token: str, token_claims: Mapping[str, Any]) -> None:
        self._tokens[token] = dict(token_claims)

    def verify(self, token: str) -> Mapping[str, Any]:
        try:
            return self._tokens[token]
        except KeyError:
            raise SignatureError("token signature is invalid") from None


def claims(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "iss": CONFIG.issuer,
        "aud": CONFIG.audience,
        "sub": "alice",
        "name": "Alice",
        "exp": int((_NOW + timedelta(minutes=5)).timestamp()),
        "nbf": int((_NOW - timedelta(minutes=5)).timestamp()),
        "groups": ["grp-content"],
    }
    base.update(overrides)
    return base


def make_provider(
    script: Mapping[str, Mapping[str, Any]],
) -> tuple[EnterpriseIdentityProvider, ScriptedVerifier]:
    verifier = ScriptedVerifier(script)
    provider = EnterpriseIdentityProvider(
        config=CONFIG,
        signature_verifier=verifier,
        group_mapping=GROUP_MAPPING,
        clock=lambda: _NOW,
    )
    return provider, verifier


class TestOidcValidation:
    def test_valid_token_yields_principal_with_mapped_roles(self) -> None:
        provider, _ = make_provider({"tok-good": claims()})
        principal = provider.authenticate("tok-good")
        assert principal.subject == "alice"
        assert principal.roles == frozenset({Role.CONTENT_CREATOR})

    def test_bad_signature_is_rejected(self) -> None:
        provider, _verifier = make_provider({})
        with pytest.raises(AuthenticationError):
            provider.authenticate("tok-unsigned")

    def test_wrong_issuer_is_rejected(self) -> None:
        provider, _verifier = make_provider({"tok": claims(iss="https://evil.example")})
        with pytest.raises(AuthenticationError):
            provider.authenticate("tok")

    def test_wrong_audience_is_rejected(self) -> None:
        provider, _verifier = make_provider({"tok": claims(aud="other-app")})
        with pytest.raises(AuthenticationError):
            provider.authenticate("tok")

    def test_expired_token_is_rejected(self) -> None:
        provider, _verifier = make_provider(
            {"tok": claims(exp=int((_NOW - timedelta(minutes=5)).timestamp()))}
        )
        with pytest.raises(AuthenticationError):
            provider.authenticate("tok")

    def test_not_yet_valid_token_is_rejected(self) -> None:
        provider, _verifier = make_provider(
            {"tok": claims(nbf=int((_NOW + timedelta(minutes=1)).timestamp()))}
        )
        with pytest.raises(AuthenticationError):
            provider.authenticate("tok")

    def test_role_claims_in_token_are_ignored(self) -> None:
        """A forged 'roles' claim must never grant roles."""
        provider, _verifier = make_provider(
            {"tok": claims(groups=[], roles=["admin", "medical_reviewer"])}
        )
        principal = provider.authenticate("tok")
        assert principal.roles == frozenset()

    def test_error_messages_never_echo_the_token(self) -> None:
        provider, _verifier = make_provider({})
        with pytest.raises(AuthenticationError) as excinfo:
            provider.authenticate("tok-sensitive-value")
        assert "tok-sensitive-value" not in str(excinfo.value)


class TestLoginFlow:
    def test_state_and_nonce_round_trip(self) -> None:
        provider, verifier = make_provider({})
        state, nonce = provider.begin_login()
        verifier.add("tok", claims(nonce=nonce))
        principal = provider.complete_login(state=state, id_token="tok")
        assert principal.subject == "alice"

    def test_unknown_state_is_rejected(self) -> None:
        provider, _verifier = make_provider({"tok": claims(nonce="n1")})
        with pytest.raises(AuthenticationError):
            provider.complete_login(state="state-never-issued", id_token="tok")

    def test_state_is_single_use(self) -> None:
        provider, verifier = make_provider({})
        state, nonce = provider.begin_login()
        verifier.add("tok", claims(nonce=nonce))
        provider.complete_login(state=state, id_token="tok")
        with pytest.raises(AuthenticationError):
            provider.complete_login(state=state, id_token="tok")

    def test_nonce_mismatch_is_rejected(self) -> None:
        provider, verifier = make_provider({})
        state, _nonce = provider.begin_login()
        verifier.add("tok", claims(nonce="different-nonce"))
        with pytest.raises(AuthenticationError):
            provider.complete_login(state=state, id_token="tok")


def test_unconfigured_provider_is_blocked_not_faked() -> None:
    """Without DEV SSO metadata the provider must refuse, never fake success."""
    provider = EnterpriseIdentityProvider(
        config=CONFIG,
        signature_verifier=None,
        group_mapping=GROUP_MAPPING,
        clock=lambda: _NOW,
    )
    with pytest.raises(ProviderNotConfiguredError):
        provider.authenticate("any-token")
