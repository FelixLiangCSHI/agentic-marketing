"""3-legged OAuth (Authorization Code) adapter — references only, mock only.

The adapter builds the authorization URL, enforces single-use bound state
(CSRF), exchanges codes and refreshes tokens through an injected
transport. Token material is only ever exposed as masked
:class:`SecretValue` handles; refresh tokens are written to the Secret
Manager and referenced, never returned raw. No real network transport
exists in this repo — real OAuth runs only in protected DEV/SIT jobs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol
from urllib.parse import urlencode

from infra_core.secrets import SecretRef, SecretResolver, SecretValue

from connector_sdk.errors import AuthExpiredError

from linkedin_connector.config import LinkedInConnectorConfig


class OAuthStateError(Exception):
    """The OAuth state is unknown, tampered with or already consumed."""


@dataclass(frozen=True)
class TokenGrant:
    """Masked token handles; refresh token lives behind a secret reference."""

    access_token: SecretValue
    expires_in_seconds: int
    refresh_token_ref: str
    scopes: tuple[str, ...]


class OAuthTransport(Protocol):
    """Token-endpoint transport; the only real implementations live in
    protected DEV/SIT jobs."""

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, object]: ...

    def refresh(self, *, refresh_token: SecretValue) -> dict[str, object]: ...


@dataclass
class MockOAuthTransport:
    """Deterministic scripted token endpoint; never touches the network."""

    fail_with: Literal["AUTH_EXPIRED"] | None = None
    calls: list[str] = field(default_factory=list)

    def _respond(self, kind: str) -> dict[str, object]:
        self.calls.append(kind)
        if self.fail_with == "AUTH_EXPIRED":
            raise AuthExpiredError("provider rejected the grant: token expired or revoked")
        return {
            "access_token": f"synthetic-access-token-{len(self.calls)}",
            "expires_in": 3600,
            "refresh_token": f"synthetic-rotated-refresh-token-{len(self.calls)}",
        }

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, object]:
        return self._respond("exchange_code")

    def refresh(self, *, refresh_token: SecretValue) -> dict[str, object]:
        return self._respond("refresh")


class OAuthAdapter:
    """Authorization Code flow with bound single-use state."""

    def __init__(
        self,
        *,
        config: LinkedInConnectorConfig,
        secret_resolver: SecretResolver,
        transport: OAuthTransport,
        redirect_uri: str,
    ) -> None:
        if not redirect_uri.startswith("https://"):
            raise ValueError("redirect_uri must be an internal https endpoint")
        self._config = config
        self._resolver = secret_resolver
        self._transport = transport
        self._redirect_uri = redirect_uri
        self._pending_states: set[str] = set()

    def authorization_url(self, *, state: str) -> str:
        """Build the official authorization URL; registers ``state`` as pending."""
        if not state:
            raise ValueError("state is required")
        client_id = self._resolver.resolve(
            SecretRef.parse(self._config.auth.client_id_ref)
        )
        self._pending_states.add(state)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id.reveal(),
                "redirect_uri": self._redirect_uri,
                "state": state,
                "scope": " ".join(self._config.auth.scopes),
            }
        )
        return f"{self._config.auth.authorization_endpoint}?{query}"

    def exchange_code(self, *, code: str, state: str) -> TokenGrant:
        """Exchange an authorization code; state must match and is single-use."""
        if state not in self._pending_states:
            raise OAuthStateError("unknown, tampered or already-consumed OAuth state")
        self._pending_states.discard(state)
        response = self._transport.exchange_code(code=code, redirect_uri=self._redirect_uri)
        return self._grant_from(response)

    def refresh_access_token(self) -> TokenGrant:
        """Refresh using the Secret Manager reference; never logs the token."""
        refresh_token = self._resolver.resolve(
            SecretRef.parse(self._config.auth.refresh_token_ref)
        )
        response = self._transport.refresh(refresh_token=refresh_token)
        return self._grant_from(response)

    def _grant_from(self, response: dict[str, object]) -> TokenGrant:
        access = SecretValue(str(response["access_token"]))
        # Rotated refresh tokens go to the Secret Manager; only the
        # reference leaves this adapter. (The mock resolver has no write
        # API — protected jobs use the real Secret Manager runbook.)
        return TokenGrant(
            access_token=access,
            expires_in_seconds=int(str(response.get("expires_in", 0))),
            refresh_token_ref=self._config.auth.refresh_token_ref,
            scopes=self._config.auth.scopes,
        )
