"""Normalized connector errors (Phase 03 / Subphase 02).

Every provider failure is a typed exception carrying ``retryable`` and
``reconcile_required``; ``normalize_error`` maps any exception onto the
frozen ``connector-error.v1`` document. Messages are sanitized: tokens,
secrets and credential-shaped material never reach logs, agents or API
responses.
"""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*:\s*)\S.*"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(
        r"(?i)\b(access_token|refresh_token|client_secret|developer_token|api[_-]?key|password)"
        r"\b\s*[=:]\s*\"?[^\s\"',}]+"
    ),
    re.compile(r"\bya29\.[A-Za-z0-9._-]+"),
    re.compile(r"\b1//[A-Za-z0-9._-]+"),
    re.compile(r"\bsk-[A-Za-z0-9]{8,}"),
    re.compile(r"\bAQ[A-Za-z0-9_-]{16,}"),
)

_REDACTED = "[redacted]"


def sanitize_message(raw: str) -> str:
    """Strip credential-shaped material from a message before it leaves."""
    sanitized = raw
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(_REDACTED, sanitized)
    return sanitized[:2000] if sanitized else "error"


class ConnectorSdkError(Exception):
    """Base class; ``code`` matches connector-error.v1 codes."""

    code: str = "connector_error"
    retryable: bool = False
    reconcile_required: bool = False

    def __init__(self, message: str = "") -> None:
        super().__init__(sanitize_message(message or self.code))


class ConfigInvalidError(ConnectorSdkError):
    """Configuration invalid or incomplete for the requested mode."""

    code = "config_invalid"


class VerificationRequiredError(ConfigInvalidError):
    """Official documentation verification missing; real modes blocked."""

    code = "verification_required"


class SchemaInvalidError(ConnectorSdkError):
    """The request violates the contract; never sent to the provider."""

    code = "schema_invalid"


class AuthExpiredError(ConnectorSdkError):
    """401/403 or expired token; retrying cannot help."""

    code = "auth_expired"


class ProviderRequestError(ConnectorSdkError):
    """Non-retryable 4xx (schema, permission, not-found, conflict)."""

    code = "provider_rejected_request"


class RateLimitedError(ConnectorSdkError):
    """HTTP 429; retryable, must honor ``Retry-After``."""

    code = "rate_limited"
    retryable = True

    def __init__(self, *, retry_after_seconds: int, message: str = "") -> None:
        super().__init__(message or f"rate limited; retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class ProviderTimeoutError(ConnectorSdkError):
    """Timeout or connection loss: side effects unknown → reconcile first."""

    code = "provider_timeout"
    retryable = True
    reconcile_required = True


class ProviderServerError(ConnectorSdkError):
    """5xx: the write may or may not have landed → reconcile first."""

    code = "provider_server_error"
    retryable = True
    reconcile_required = True


def normalize_error(
    *,
    connector: str,
    error: Exception,
    trace_id: str,
    occurred_at: str,
) -> dict[str, Any]:
    """Map any exception onto the frozen ``connector-error.v1`` shape."""
    if isinstance(error, ConnectorSdkError):
        code = error.code
        retryable = error.retryable
        reconcile_required = error.reconcile_required
        message = sanitize_message(str(error))
        details: dict[str, Any] = {"reconcile_required": reconcile_required}
        if isinstance(error, RateLimitedError):
            details["retry_after_seconds"] = error.retry_after_seconds
    else:
        code = "connector_internal"
        retryable = False
        message = sanitize_message(f"{type(error).__name__}: {error}")
        details = {"reconcile_required": False}
    return {
        "schema_version": "1.0",
        "connector": connector,
        "code": code,
        "message": message,
        "trace_id": trace_id,
        "retryable": retryable,
        "details": details,
        "occurred_at": occurred_at,
    }
