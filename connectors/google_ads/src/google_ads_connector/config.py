"""Google Ads connector configuration: strict, reference-only, mock-first.

Loads ``config/google_ads.yaml``. The API version is injected from
configuration (never hardcoded), the Developer Token / client secret /
refresh token must be ``secretref://`` Secret Manager references (env or
config refs are not acceptable for true secrets), customer IDs and quota
are references only, GAQL via the official ``GoogleAdsService`` is the
only reporting surface, and Service Account usage is locked behind the
``service_account_approved`` method + ``use_service_account`` pair that
exists only for approved enterprise-owned accounts — OAuth is the
default. Sandbox/live require recorded official verification.
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

_OFFICIAL_API_HOSTS = frozenset({"googleads.googleapis.com"})

Mode = Literal["mock", "sandbox", "live"]


def _require_ref(value: str) -> str:
    if not _REF_PATTERN.match(value):
        raise ValueError(
            "value must be a secretref:// / env:// / config:// reference, never a literal"
        )
    return value


def _require_secretref(value: str) -> str:
    _require_ref(value)
    if not value.startswith("secretref://"):
        raise ValueError(
            "true secrets (developer token, client secret, refresh token) must be "
            "secretref:// Secret Manager references"
        )
    return value


class _Section(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


class EndpointConfig(_Section):
    base_url: str
    api_version_ref: str
    verify_tls: Literal[True]
    official_docs: tuple[str, ...] = pydantic.Field(min_length=1)
    verification: Literal["required-before-sandbox-or-live", "verified", "blocked"]

    @pydantic.field_validator("base_url")
    @classmethod
    def _official_base(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or (parsed.hostname or "") not in _OFFICIAL_API_HOSTS:
            raise ValueError(
                f"url must be the official https Google Ads endpoint, got {value!r}"
            )
        return value

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
    method: Literal["oauth", "service_account_approved"]
    developer_token_ref: str
    oauth_client_id_ref: str
    oauth_client_secret_ref: str
    refresh_token_ref: str
    redirect_uri_ref: str
    use_service_account: bool
    service_account_identity_ref: str
    service_account_approval_ref: str
    rotation_runbook: str = pydantic.Field(min_length=1)

    @pydantic.field_validator(
        "developer_token_ref", "oauth_client_secret_ref", "refresh_token_ref"
    )
    @classmethod
    def _secretref_only(cls, value: str) -> str:
        return _require_secretref(value)

    @pydantic.field_validator(
        "oauth_client_id_ref",
        "redirect_uri_ref",
        "service_account_identity_ref",
        "service_account_approval_ref",
    )
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)

    @pydantic.model_validator(mode="after")
    def _service_account_gate(self) -> "AuthConfig":
        if self.use_service_account != (self.method == "service_account_approved"):
            raise ValueError(
                "use_service_account may only (and must) be true together with "
                "method='service_account_approved' — Service Accounts are allowed "
                "solely for approved enterprise-owned accounts; OAuth is the default"
            )
        return self


class AccountConfig(_Section):
    customer_id_ref: str
    login_customer_id_ref: str
    manager_account_required: Literal[True]
    test_account_required: Literal[True]
    enterprise_owned_account_required_for_service_account: Literal[True]

    @pydantic.field_validator("customer_id_ref", "login_customer_id_ref")
    @classmethod
    def _ref_only(cls, value: str) -> str:
        return _require_ref(value)


class RateLimitConfig(_Section):
    requests_per_window_ref: str
    daily_operations_quota_ref: str
    window_seconds: int = pydantic.Field(ge=1)

    @pydantic.field_validator("requests_per_window_ref", "daily_operations_quota_ref")
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


class QueryConfig(_Section):
    reporting_service: Literal["GoogleAdsService"]
    query_language: Literal["GAQL"]
    stream_mode: Literal["Search", "SearchStream"]


class FaultInjectionConfig(_Section):
    enabled: Literal[True]
    scenarios: tuple[str, ...] = pydantic.Field(min_length=1)


class MockConfig(_Section):
    deterministic: Literal[True]
    seed: int
    fixture_set: str = pydantic.Field(min_length=1)
    fault_fixture_set: str = pydantic.Field(min_length=1)
    fault_injection: FaultInjectionConfig


class GoogleAdsConnectorConfig(_Section):
    """Authoritative ``config/google_ads.yaml`` document."""

    schema_version: Literal["1.0"]
    provider: Literal["google_ads"]
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
    query: QueryConfig
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


def load_google_ads_config(path: Path) -> GoogleAdsConnectorConfig:
    """Load and strictly validate ``config/google_ads.yaml``."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return GoogleAdsConnectorConfig.model_validate(document)
