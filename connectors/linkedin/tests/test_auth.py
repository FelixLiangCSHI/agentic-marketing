"""RED tests: 3-legged OAuth adapter (Authorization Code flow, mock only).

Tokens live only in the Secret Manager: the adapter returns masked
``SecretValue`` handles and a stored secret reference; raw token material
never appears in URLs it builds (except the non-secret client_id), logs
or exceptions. State is bound and single-use (CSRF protection). No real
network calls occur in this repo — the token endpoint is an injected
transport.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from infra_core.secrets import FakeSecretResolver

from linkedin_connector import (
    MockOAuthTransport,
    OAuthAdapter,
    OAuthStateError,
)
from connector_sdk import AuthExpiredError

from builders import make_config


def make_adapter(
    *, transport: MockOAuthTransport | None = None
) -> tuple[OAuthAdapter, FakeSecretResolver]:
    resolver = FakeSecretResolver()
    resolver._store["secretref://vault/dmt/dev/linkedin/client-id"] = "client-id-public"
    resolver._store["secretref://vault/dmt/dev/linkedin/client-secret"] = "synthetic-client-secret"
    resolver._store["secretref://vault/dmt/dev/linkedin/refresh-token"] = "synthetic-refresh-token"
    adapter = OAuthAdapter(
        config=make_config(),
        secret_resolver=resolver,
        transport=transport if transport is not None else MockOAuthTransport(),
        redirect_uri="https://oauth-broker.internal.example/callback",
    )
    return adapter, resolver


def test_authorization_url_uses_config_endpoints_and_state() -> None:
    adapter, _ = make_adapter()
    url = adapter.authorization_url(state="state-p3-0001")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.hostname == "www.linkedin.com"
    query = parse_qs(parsed.query)
    assert query["response_type"] == ["code"]
    assert query["state"] == ["state-p3-0001"]
    assert query["client_id"] == ["client-id-public"]
    assert query["redirect_uri"] == ["https://oauth-broker.internal.example/callback"]
    assert set(query["scope"][0].split(" ")) == {"rw_ads", "r_ads", "r_ads_reporting"}


def test_redirect_uri_must_be_https() -> None:
    resolver = FakeSecretResolver()
    with pytest.raises(ValueError):
        OAuthAdapter(
            config=make_config(),
            secret_resolver=resolver,
            transport=MockOAuthTransport(),
            redirect_uri="http://oauth-broker.internal.example/callback",
        )


def test_client_secret_never_in_authorization_url() -> None:
    adapter, _ = make_adapter()
    url = adapter.authorization_url(state="state-p3-0002")
    assert "synthetic-client-secret" not in url


def test_exchange_code_returns_masked_tokens_and_stores_reference() -> None:
    adapter, resolver = make_adapter()
    adapter.authorization_url(state="state-p3-0003")
    grant = adapter.exchange_code(code="auth-code-0001", state="state-p3-0003")
    assert str(grant.access_token) == "****"
    assert repr(grant.access_token) == "SecretValue(****)"
    assert grant.refresh_token_ref.startswith("secretref://")
    # the refresh token was written to the secret manager, not returned raw
    assert "raw" not in repr(grant)


def test_state_mismatch_rejected() -> None:
    adapter, _ = make_adapter()
    adapter.authorization_url(state="state-p3-0004")
    with pytest.raises(OAuthStateError):
        adapter.exchange_code(code="auth-code-0002", state="state-tampered")


def test_state_is_single_use() -> None:
    adapter, _ = make_adapter()
    adapter.authorization_url(state="state-p3-0005")
    adapter.exchange_code(code="auth-code-0003", state="state-p3-0005")
    with pytest.raises(OAuthStateError):
        adapter.exchange_code(code="auth-code-0003", state="state-p3-0005")


def test_refresh_uses_secret_reference_and_masks_result() -> None:
    adapter, _ = make_adapter()
    grant = adapter.refresh_access_token()
    assert str(grant.access_token) == "****"


def test_expired_refresh_token_raises_auth_expired() -> None:
    adapter, _ = make_adapter(transport=MockOAuthTransport(fail_with="AUTH_EXPIRED"))
    with pytest.raises(AuthExpiredError):
        adapter.refresh_access_token()


def test_error_messages_never_carry_token_material() -> None:
    adapter, _ = make_adapter(transport=MockOAuthTransport(fail_with="AUTH_EXPIRED"))
    with pytest.raises(AuthExpiredError) as excinfo:
        adapter.refresh_access_token()
    assert "synthetic-refresh-token" not in str(excinfo.value)
