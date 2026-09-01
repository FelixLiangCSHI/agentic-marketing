"""Shared channel connector configuration (strict, reference-only).

Every credential, API version and quota is a reference
(``secretref://`` / ``env://`` / ``config://``) — raw values never
validate. Non-negotiable safety flags (proxy required, no inbound,
reconcile-before-retry, honor Retry-After) are enforced at the type
level with ``Literal``. Sandbox/live additionally require recorded
official verification and an explicit enabled flag.
"""

from __future__ import annotations

import re
from typing import Literal

import pydantic

from connector_sdk.errors import ConfigInvalidError

_REF_PATTERN = re.compile(r"^(secretref://|env://|config://)[A-Za-z0-9][A-Za-z0-9/_.-]*$")

Mode = Literal["mock", "sandbox", "live"]


def _require_ref(value: str) -> str:
    if not _REF_PATTERN.match(value):
        raise ValueError(
            "value must be a secretref:// / env:// / config:// reference, never a literal"
        )
    return value


class _Section(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class EndpointConfig(_Section):
    base_url: str
    api_version_ref: str
    verify_tls: Literal[True]
    verification: Literal["required-before-sandbox-or-live", "verified", "blocked"]

    @pydantic.field_validator("base_url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("base_url must use https")
        return value

    @pydantic.field_validator("api_version_ref")
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)


class AuthConfig(_Section):
    method: Literal["oauth_3legged", "oauth_client_credentials", "api_key"]
    client_id_ref: str
    client_secret_ref: str
    refresh_token_ref: str | None = None

    @pydantic.field_validator("client_id_ref", "client_secret_ref", "refresh_token_ref")
    @classmethod
    def _ref_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_ref(value)


class RateLimitConfig(_Section):
    requests_per_window_ref: str
    window_seconds: int = pydantic.Field(ge=1)

    @pydantic.field_validator("requests_per_window_ref")
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)


class RetryStrategyConfig(_Section):
    max_attempts: int = pydantic.Field(ge=1, le=10)
    reconcile_before_retry: Literal[True]
    honor_retry_after: Literal[True]
    base_delay_seconds: int = pydantic.Field(ge=1)
    max_delay_seconds: int = pydantic.Field(ge=1)


class TimeoutsConfig(_Section):
    connect_seconds: int = pydantic.Field(ge=1)
    read_seconds: int = pydantic.Field(ge=1)
    total_seconds: int = pydantic.Field(ge=1)


class ProxyConfig(_Section):
    required: Literal[True]
    url_ref: str
    allow_inbound: Literal[False]

    @pydantic.field_validator("url_ref")
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)


class MockConfig(_Section):
    deterministic: Literal[True]
    seed: int


class ChannelConnectorConfig(_Section):
    """Authoritative connector configuration document."""

    schema_version: Literal["1.0"]
    provider: str = pydantic.Field(min_length=1)
    connector: str = pydantic.Field(min_length=1)
    enabled: bool
    mode: Mode
    endpoint: EndpointConfig
    auth: AuthConfig
    rate_limit: RateLimitConfig
    retry_strategy: RetryStrategyConfig
    timeouts: TimeoutsConfig
    proxy: ProxyConfig
    mock: MockConfig

    def require_ready_for_mode(self) -> None:
        """Raise unless the connector may run in its configured mode.

        Mock always passes. Sandbox/live require ``enabled=True`` and
        endpoint verification recorded as ``verified``.
        """
        if self.mode == "mock":
            return
        if self.endpoint.verification != "verified":
            raise ConfigInvalidError(
                f"mode {self.mode} requires endpoint verification=='verified' "
                f"(got {self.endpoint.verification!r}); record official docs verification first"
            )
        if not self.enabled:
            raise ConfigInvalidError(
                f"mode {self.mode} requires enabled=True (explicit human enablement)"
            )
