"""Typed errors and the normalized ConnectorError contract (jimeng).

Every provider failure surfaces as a typed exception; ``normalize_error``
maps it onto the frozen ``connector-error.v1`` contract. Cookie or other
non-official auth is an immediate hard failure — never a fallback.
Messages never carry prompts, result URLs, bodies or secret material.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr


class JimengConnectorError(Exception):
    """Base class; ``code`` matches connector-error.v1 codes."""

    code: str = "connector_error"
    retryable: bool = False


class ConnectorConfigError(JimengConnectorError):
    """Configuration invalid or incomplete for the requested mode."""

    code = "config_invalid"


class ForbiddenAuthError(JimengConnectorError):
    """Cookie/reverse-engineered/non-official auth: immediate FAIL."""

    code = "forbidden_auth_method"


class RealModeBlockedError(JimengConnectorError):
    """sandbox/live requested without approvals; hard stop."""

    code = "real_mode_blocked"


class NotSupportedError(JimengConnectorError):
    """The connector does not support this action or capability."""

    code = "not_supported"


class RequestInvalidError(JimengConnectorError):
    """The job request violates the contract; never sent."""

    code = "request_invalid"


class AuthenticationError(JimengConnectorError):
    """401/403 from the provider; retrying cannot help."""

    code = "auth_failed"


class ProviderRequestError(JimengConnectorError):
    """Non-retryable 4xx (schema, not-found, conflict, unprocessable)."""

    code = "provider_rejected_request"


class ProviderRateLimitedError(JimengConnectorError):
    """429 after retries were exhausted."""

    code = "rate_limited"
    retryable = True


class CreateTimeoutError(JimengConnectorError):
    """Create call timed out; reconcile by idempotency before retrying."""

    code = "create_timeout"
    retryable = True


class ProviderServerError(JimengConnectorError):
    """5xx after retries were exhausted."""

    code = "provider_server_error"
    retryable = True


class JobFailedError(JimengConnectorError):
    """The provider reported the job as failed."""

    code = "provider_job_failed"


class JobCancelledError(JimengConnectorError):
    """The job was cancelled (locally or provider-side)."""

    code = "job_cancelled"


class UnknownJobError(JimengConnectorError):
    """Provider does not know the job: stop creating, human reconcile/DLQ."""

    code = "unknown_job"


class ResultUrlExpiredError(JimengConnectorError):
    """Temporary result URL expired; re-fetch result reference, not create."""

    code = "result_url_expired"
    retryable = True


class AssetValidationError(JimengConnectorError):
    """Downloaded asset failed TLS/MIME/size/hash validation."""

    code = "asset_validation_failed"


class MalwareRejectedError(JimengConnectorError):
    """Malware scan rejected the downloaded asset."""

    code = "malware_rejected"


class BudgetExceededError(JimengConnectorError):
    """Per-run/daily budget or per-run asset cap reached its stop line."""

    code = "budget_exceeded"


class LocalQueueFullError(JimengConnectorError):
    """Local RPM/concurrency/jobs-per-day limit rejected the request."""

    code = "local_queue_full"
    retryable = True


class PollDeadlineExceededError(JimengConnectorError):
    """Job did not finish within async_job.max_duration_ms."""

    code = "poll_deadline_exceeded"


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
