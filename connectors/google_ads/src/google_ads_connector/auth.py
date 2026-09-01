"""Google Ads auth adapter — references only, mock only.

OAuth (refresh-token grant) is the default. The Developer Token is only
ever resolved from its ``secretref://`` reference and exposed as a masked
:class:`SecretValue`. The Service Account branch exists solely for
approved enterprise-owned accounts: without a recorded approval whose
``approved`` and ``enterprise_owned_account`` flags are both true it
fails closed with :class:`ServiceAccountNotApprovedError` (never falls
back silently). No real network transport exists in this repo — real
token exchanges run only in protected DEV/SIT jobs via Workload Identity
or the OAuth broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Protocol

from infra_core.secrets import SecretRef, SecretResolver, SecretValue

from connector_sdk.errors import AuthExpiredError, ConnectorSdkError

from google_ads_connector.config import GoogleAdsConnectorConfig


class DeveloperTokenInvalidError(ConnectorSdkError):
    """The Developer Token was rejected; requires human rotation, no retry."""

    code = "developer_token_invalid"
    retryable = False
    reconcile_required = False


class ServiceAccountNotApprovedError(ConnectorSdkError):
    """Service Account use without a recorded enterprise-ownership approval."""

    code = "service_account_not_approved"
    retryable = False
    reconcile_required = False


@dataclass(frozen=True)
class GoogleAdsCredentials:
    """Masked credential handles; raw values never leave the adapter."""

    developer_token: SecretValue
    access_token: SecretValue
    expires_in_seconds: int
    login_customer_id_ref: str
    identity_ref: str | None


class TokenTransport(Protocol):
    """Token-endpoint transport; real implementations live only in
    protected DEV/SIT jobs."""

    def refresh(self, *, refresh_token: SecretValue) -> dict[str, object]: ...

    def mint_identity_token(self, *, identity_ref: str) -> dict[str, object]: ...


@dataclass
class MockTokenTransport:
    """Deterministic scripted token endpoint; never touches the network."""

    fail_with: Literal["AUTH_EXPIRED", "DEVELOPER_TOKEN_INVALID"] | None = None
    calls: list[str] = field(default_factory=list)

    def _respond(self, kind: str) -> dict[str, object]:
        self.calls.append(kind)
        if self.fail_with == "AUTH_EXPIRED":
            raise AuthExpiredError(
                "provider rejected the request: access token expired or revoked"
            )
        if self.fail_with == "DEVELOPER_TOKEN_INVALID":
            raise DeveloperTokenInvalidError(
                "developer token rejected; rotate via the token-rotation runbook"
            )
        return {
            "access_token": f"synthetic-access-token-{len(self.calls)}",
            "expires_in": 3600,
        }

    def refresh(self, *, refresh_token: SecretValue) -> dict[str, object]:
        return self._respond("refresh")

    def mint_identity_token(self, *, identity_ref: str) -> dict[str, object]:
        return self._respond("mint_identity_token")


class GoogleAdsAuthAdapter:
    """OAuth-by-default credential minting with a fail-closed SA branch."""

    def __init__(
        self,
        *,
        config: GoogleAdsConnectorConfig,
        secret_resolver: SecretResolver,
        transport: TokenTransport,
    ) -> None:
        self._config = config
        self._resolver = secret_resolver
        self._transport = transport

    def mint_credentials(
        self, *, service_account_approval: Mapping[str, object] | None = None
    ) -> GoogleAdsCredentials:
        """Mint masked credentials for the configured auth method."""
        developer_token = self._resolver.resolve(
            SecretRef.parse(self._config.auth.developer_token_ref)
        )
        if self._config.auth.use_service_account:
            response = self._mint_via_service_account(service_account_approval)
            identity_ref: str | None = self._config.auth.service_account_identity_ref
        else:
            response = self._mint_via_oauth()
            identity_ref = None
        return GoogleAdsCredentials(
            developer_token=developer_token,
            access_token=SecretValue(str(response["access_token"])),
            expires_in_seconds=int(str(response.get("expires_in", 0))),
            login_customer_id_ref=self._config.account.login_customer_id_ref,
            identity_ref=identity_ref,
        )

    def _mint_via_oauth(self) -> dict[str, object]:
        refresh_token = self._resolver.resolve(
            SecretRef.parse(self._config.auth.refresh_token_ref)
        )
        return self._transport.refresh(refresh_token=refresh_token)

    def _mint_via_service_account(
        self, approval: Mapping[str, object] | None
    ) -> dict[str, object]:
        if (
            approval is None
            or approval.get("approved") is not True
            or approval.get("enterprise_owned_account") is not True
        ):
            raise ServiceAccountNotApprovedError(
                "service account use requires a recorded Security/IAM approval for an "
                "enterprise-owned account; use OAuth otherwise"
            )
        return self._transport.mint_identity_token(
            identity_ref=self._config.auth.service_account_identity_ref
        )
