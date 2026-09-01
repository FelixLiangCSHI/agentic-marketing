"""LinkedIn connector configuration: strict, reference-only, mock-first.

Loads ``config/linkedin.yaml``. The API version is injected from
configuration (never hardcoded), credentials/quota are references only
(``secretref://`` / ``env://`` / ``config://``), scopes cannot exceed the
approved minimal set, OAuth endpoints must be the official LinkedIn HTTPS
endpoints and the non-negotiable safety flags are enforced with
``Literal``. Sandbox/live require recorded official verification.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import pydantic
import yaml

from connector_sdk.errors import ConfigInvalidError

_REF_PATTERN = re.compile(r"^(secretref://|env://|config://)[A-Za-z0-9][A-Za-z0-9/_.-]*$")

APPROVED_SCOPES = frozenset({"rw_ads", "r_ads", "r_ads_reporting"})

_OFFICIAL_OAUTH_HOSTS = frozenset({"www.linkedin.com"})
_OFFICIAL_API_HOSTS = frozenset({"api.linkedin.com"})

Mode = Literal["mock", "sandbox", "live"]


def _require_ref(value: str) -> str:
    if not _REF_PATTERN.match(value):
        raise ValueError(
            "value must be a secretref:// / env:// / config:// reference, never a literal"
        )
    return value


def _require_official_https(value: str, hosts: frozenset[str]) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or (parsed.hostname or "") not in hosts:
        raise ValueError(f"url must be an official https LinkedIn endpoint, got {value!r}")
    return value


class _Section(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class EndpointConfig(_Section):
    base_url: str
    api_version_ref: str
    resource_prefix: Literal["/rest"]
    verify_tls: Literal[True]
    official_docs: tuple[str, ...] = pydantic.Field(min_length=1)
    verification: Literal["required-before-sandbox-or-live", "verified", "blocked"]

    @pydantic.field_validator("base_url")
    @classmethod
    def _official_base(cls, value: str) -> str:
        return _require_official_https(value, _OFFICIAL_API_HOSTS)

    @pydantic.field_validator("api_version_ref")
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)

    @pydantic.field_validator("official_docs")
    @classmethod
    def _docs_https(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for url in value:
            if not url.startswith("https://"):
                raise ValueError("official_docs must be https URLs")
        return value


class AuthConfig(_Section):
    method: Literal["oauth_3legged"]
    client_id_ref: str
    client_secret_ref: str
    refresh_token_ref: str
    redirect_uri_ref: str
    scopes: tuple[str, ...] = pydantic.Field(min_length=1)
    token_endpoint: str
    authorization_endpoint: str
    rotation_runbook: str = pydantic.Field(min_length=1)

    @pydantic.field_validator(
        "client_id_ref", "client_secret_ref", "refresh_token_ref", "redirect_uri_ref"
    )
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)

    @pydantic.field_validator("scopes")
    @classmethod
    def _approved_scopes_only(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        extra = set(value) - APPROVED_SCOPES
        if extra:
            raise ValueError(
                f"scopes {sorted(extra)} exceed the approved minimal set {sorted(APPROVED_SCOPES)}"
            )
        return value

    @pydantic.field_validator("token_endpoint", "authorization_endpoint")
    @classmethod
    def _official_oauth(cls, value: str) -> str:
        return _require_official_https(value, _OFFICIAL_OAUTH_HOSTS)


class AccountConfig(_Section):
    account_id_ref: str
    test_account_required: Literal[True]
    production_access_tier_ref: str

    @pydantic.field_validator("account_id_ref", "production_access_tier_ref")
    @classmethod
    def _ref_only(cls, value: str) -> str:
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


class FaultInjectionConfig(_Section):
    enabled: Literal[True]
    scenarios: tuple[str, ...] = pydantic.Field(min_length=1)


class MockConfig(_Section):
    deterministic: Literal[True]
    seed: int
    fixture_set: str = pydantic.Field(min_length=1)
    fault_fixture_set: str = pydantic.Field(min_length=1)
    fault_injection: FaultInjectionConfig


class LinkedInConnectorConfig(_Section):
    """Authoritative ``config/linkedin.yaml`` document."""

    schema_version: Literal["1.0"]
    provider: Literal["linkedin"]
    connector: str = pydantic.Field(min_length=1)
    enabled: bool
    mode: Mode
    endpoint: EndpointConfig
    auth: AuthConfig
    account: AccountConfig
    rate_limit: RateLimitConfig
    retry_strategy: RetryStrategyConfig
    timeouts: TimeoutsConfig
    proxy: ProxyConfig
    mock: MockConfig

    def require_ready_for_mode(self) -> None:
        """Raise unless the connector may run in its configured mode."""
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


def load_linkedin_config(path: Path) -> LinkedInConnectorConfig:
    """Load and strictly validate ``config/linkedin.yaml``."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LinkedInConnectorConfig.model_validate(document)
