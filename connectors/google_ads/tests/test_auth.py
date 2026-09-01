"""Auth adapter tests: OAuth default, Developer Token stays masked, token
expiry surfaces as AUTH_EXPIRED, invalid Developer Token is non-retryable,
and the Service Account branch fails closed without a recorded approval."""

from __future__ import annotations

import pytest

from infra_core.secrets import FakeSecretResolver

from connector_sdk.errors import AuthExpiredError

from google_ads_connector import (
    DeveloperTokenInvalidError,
    GoogleAdsAuthAdapter,
    MockTokenTransport,
    ServiceAccountNotApprovedError,
)

from builders import config_document, make_config


def make_resolver() -> FakeSecretResolver:
    resolver = FakeSecretResolver()
    document = config_document()
    resolver._store[document["auth"]["developer_token_ref"]] = "synthetic-developer-token"
    resolver._store[document["auth"]["oauth_client_id_ref"]] = "synthetic-client-id"
    resolver._store[document["auth"]["oauth_client_secret_ref"]] = "synthetic-client-secret"
    resolver._store[document["auth"]["refresh_token_ref"]] = "synthetic-refresh-token"
    return resolver


class TestOAuthPath:
    def test_mints_masked_credentials(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=make_config(), secret_resolver=make_resolver(), transport=MockTokenTransport()
        )
        credentials = adapter.mint_credentials()
        assert str(credentials.developer_token) == "****"
        assert str(credentials.access_token) == "****"
        assert "synthetic" not in repr(credentials)
        assert credentials.login_customer_id_ref.startswith("config://")
        assert credentials.expires_in_seconds > 0

    def test_token_expiry_maps_to_auth_expired(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=make_config(),
            secret_resolver=make_resolver(),
            transport=MockTokenTransport(fail_with="AUTH_EXPIRED"),
        )
        with pytest.raises(AuthExpiredError):
            adapter.mint_credentials()

    def test_invalid_developer_token_is_non_retryable(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=make_config(),
            secret_resolver=make_resolver(),
            transport=MockTokenTransport(fail_with="DEVELOPER_TOKEN_INVALID"),
        )
        with pytest.raises(DeveloperTokenInvalidError) as excinfo:
            adapter.mint_credentials()
        assert excinfo.value.retryable is False


class TestServiceAccountGate:
    def _sa_config(self) -> object:
        document = config_document()
        document["auth"]["method"] = "service_account_approved"
        document["auth"]["use_service_account"] = True
        return make_config(auth=document["auth"])

    def test_service_account_without_approval_record_fails_closed(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=self._sa_config(),  # type: ignore[arg-type]
            secret_resolver=make_resolver(),
            transport=MockTokenTransport(),
        )
        with pytest.raises(ServiceAccountNotApprovedError):
            adapter.mint_credentials()

    def test_service_account_with_incomplete_approval_fails_closed(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=self._sa_config(),  # type: ignore[arg-type]
            secret_resolver=make_resolver(),
            transport=MockTokenTransport(),
        )
        with pytest.raises(ServiceAccountNotApprovedError):
            adapter.mint_credentials(
                service_account_approval={"approved": True, "enterprise_owned_account": False}
            )

    def test_service_account_with_recorded_approval_uses_workload_identity(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=self._sa_config(),  # type: ignore[arg-type]
            secret_resolver=make_resolver(),
            transport=MockTokenTransport(),
        )
        credentials = adapter.mint_credentials(
            service_account_approval={
                "approved": True,
                "enterprise_owned_account": True,
                "approval_ref": "config://approvals/google-ads/service-account",
            }
        )
        assert str(credentials.access_token) == "****"
        assert credentials.identity_ref == "config://identity/google-ads/workload-identity"

    def test_oauth_config_ignores_service_account_approval(self) -> None:
        adapter = GoogleAdsAuthAdapter(
            config=make_config(), secret_resolver=make_resolver(), transport=MockTokenTransport()
        )
        credentials = adapter.mint_credentials(
            service_account_approval={"approved": True, "enterprise_owned_account": True}
        )
        assert credentials.identity_ref is None
