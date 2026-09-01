"""HTTP, proxy and retry abstractions (no real network client in repo).

Connectors depend only on the injected :class:`HttpClient`,
:class:`ProxyPolicy`, ``infra_core`` ``SecretResolver`` and ``Clock``.
The deterministic :class:`FakeHttpClient` records every call so tests can
assert that dry-run performs zero external requests. The real transport
is injected by the approved DEV/SIT pipeline — never implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol
from urllib.parse import urlparse

from connector_sdk.errors import (
    ConnectorSdkError,
    ProviderTimeoutError,
    RateLimitedError,
)


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpClient(Protocol):
    def send(self, request: HttpRequest) -> HttpResponse: ...


@dataclass(frozen=True)
class ProxyPolicy:
    """Outbound-only egress through the approved proxy and FQDN allowlist."""

    required: bool
    allowed_fqdns: tuple[str, ...]

    def validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ConnectorSdkError(f"only https egress is allowed, got {parsed.scheme}")
        host = parsed.hostname or ""
        if host not in self.allowed_fqdns:
            raise ConnectorSdkError(f"fqdn {host} is not on the approved allowlist")


@dataclass
class FakeHttpClient:
    """Deterministic scripted client; records calls, never touches network."""

    responses: list[HttpResponse] = field(default_factory=list)
    calls: list[HttpRequest] = field(default_factory=list)

    def send(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        if not self.responses:
            return HttpResponse(status_code=200, headers={}, body=b"{}")
        return self.responses.pop(0)


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff that always honors ``Retry-After``.

    A write whose outcome is unknown (timeout / 5xx with possible side
    effects) may only be retried after reconciliation confirmed that no
    external object was created (``reconciled=True``).
    """

    max_attempts: int
    base_delay_seconds: int
    max_delay_seconds: int

    def delay_before_attempt(
        self, *, attempt: int, retry_after_seconds: int | None
    ) -> int:
        if retry_after_seconds is not None:
            return retry_after_seconds
        delay = self.base_delay_seconds * int(2 ** max(attempt - 2, 0))
        return min(delay, self.max_delay_seconds)

    def should_retry(
        self, *, attempt: int, error: Exception, reconciled: bool = False
    ) -> bool:
        if attempt >= self.max_attempts:
            return False
        if not isinstance(error, ConnectorSdkError) or not error.retryable:
            return False
        if error.reconcile_required and not reconciled:
            return False
        return True

    def retry_after_from(self, error: Exception) -> int | None:
        if isinstance(error, RateLimitedError):
            return error.retry_after_seconds
        return None


__all__ = [
    "FakeHttpClient",
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "ProviderTimeoutError",
    "ProxyPolicy",
    "RetryPolicy",
]
