"""Typed errors and the normalized ConnectorError contract.

Every provider failure surfaces as a typed exception; ``normalize_error``
maps it onto the frozen ``connector-error.v1`` cross-language contract.
No error path silently falls back to mock or fabricates success.
Messages never contain request/response bodies or secret material.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr


class DeepSeekConnectorError(Exception):
    """Base class; ``code`` matches connector-error.v1 codes."""

    code: str = "connector_error"
    retryable: bool = False


class ConnectorConfigError(DeepSeekConnectorError):
    """Configuration invalid or incomplete for the requested mode."""

    code = "config_invalid"


class RealModeBlockedError(DeepSeekConnectorError):
    """sandbox/live requested without approvals/credentials; hard stop."""

    code = "real_mode_blocked"


class NotSupportedError(DeepSeekConnectorError):
    """The connector does not support this action (sync chat only)."""

    code = "not_supported"


class RequestInvalidError(DeepSeekConnectorError):
    """The outbound request violates the request contract; never sent."""

    code = "request_invalid"


class AuthenticationError(DeepSeekConnectorError):
    """401/403 from the provider; retrying cannot help."""

    code = "auth_failed"


class ProviderRequestError(DeepSeekConnectorError):
    """Non-retryable 4xx (schema, not-found, conflict, unprocessable)."""

    code = "provider_rejected_request"


class ProviderRateLimitedError(DeepSeekConnectorError):
    """429 after retries were exhausted."""

    code = "rate_limited"
    retryable = True


class ProviderTimeoutError(DeepSeekConnectorError):
    """Connect/request timeout after retries were exhausted."""

    code = "provider_timeout"
    retryable = True


class ProviderServerError(DeepSeekConnectorError):
    """5xx after retries were exhausted."""

    code = "provider_server_error"
    retryable = True


class ProviderRefusalError(DeepSeekConnectorError):
    """The model refused the request (safety/policy refusal)."""

    code = "provider_refusal"


class TokenLimitExceededError(DeepSeekConnectorError):
    """Output truncated by token limit; result is unusable, not padded."""

    code = "token_limit_exceeded"


class InvalidProviderOutputError(DeepSeekConnectorError):
    """Response body is not the promised structured output."""

    code = "invalid_provider_output"


class BudgetExceededError(DeepSeekConnectorError):
    """Per-run or daily cost budget reached its stop threshold."""

    code = "budget_exceeded"


class LocalQueueFullError(DeepSeekConnectorError):
    """Local concurrency/rate queue rejected the request."""

    code = "local_queue_full"
    retryable = True


ConnectorKind = Literal["llm", "embedding", "jimeng", "linkedin", "google_ads"]


class ConnectorErrorV1(BaseModel):
    """Mirror of ``domain-contracts/schemas/connector-error.v1.schema.json``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    connector: ConnectorKind
    code: Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9_]{1,63}$")]
    message: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    trace_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    retryable: StrictBool
    details: dict[str, Any] | None
    occurred_at: Annotated[
        StrictStr,
        Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"),
    ]
