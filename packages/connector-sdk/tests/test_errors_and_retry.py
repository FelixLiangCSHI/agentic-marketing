"""RED tests: error normalization and retry semantics.

Every provider failure maps onto the frozen ``connector-error.v1``
contract, carries ``retryable`` and ``reconcile_required`` classification,
and never leaks secrets, tokens or raw provider bodies. 429 must honor
``Retry-After``; unknown external write outcomes force reconcile before
retry.
"""

from __future__ import annotations

import pytest

from connector_sdk import (
    AuthExpiredError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    RateLimitedError,
    RetryPolicy,
    normalize_error,
    sanitize_message,
)

OCCURRED_AT = "2026-09-14T00:00:00Z"


def _normalize(exc: Exception) -> dict[str, object]:
    return normalize_error(
        connector="linkedin", error=exc, trace_id="trace-0001", occurred_at=OCCURRED_AT
    )


def test_rate_limited_is_retryable_and_carries_retry_after() -> None:
    document = _normalize(RateLimitedError(retry_after_seconds=17))
    assert document["retryable"] is True
    assert document["code"] == "rate_limited"
    details = document["details"]
    assert isinstance(details, dict)
    assert details["retry_after_seconds"] == 17
    assert details["reconcile_required"] is False


def test_timeout_requires_reconcile_before_retry() -> None:
    document = _normalize(ProviderTimeoutError("write may have side effects"))
    assert document["retryable"] is True
    details = document["details"]
    assert isinstance(details, dict)
    assert details["reconcile_required"] is True


def test_server_error_requires_reconcile() -> None:
    document = _normalize(ProviderServerError("HTTP 502"))
    assert document["retryable"] is True
    details = document["details"]
    assert isinstance(details, dict)
    assert details["reconcile_required"] is True


def test_request_error_not_retryable() -> None:
    document = _normalize(ProviderRequestError("HTTP 400 schema invalid"))
    assert document["retryable"] is False
    details = document["details"]
    assert isinstance(details, dict)
    assert details["reconcile_required"] is False


def test_auth_expired_not_retryable() -> None:
    document = _normalize(AuthExpiredError("token expired"))
    assert document["retryable"] is False
    assert document["code"] == "auth_expired"


def test_unexpected_exception_maps_to_internal_error() -> None:
    document = _normalize(ValueError("boom"))
    assert document["code"] == "connector_internal"
    assert document["retryable"] is False


def test_normalized_error_matches_contract_shape() -> None:
    document = _normalize(RateLimitedError(retry_after_seconds=1))
    assert set(document) == {
        "schema_version",
        "connector",
        "code",
        "message",
        "trace_id",
        "retryable",
        "details",
        "occurred_at",
    }
    assert document["schema_version"] == "1.0"
    assert document["connector"] == "linkedin"
    assert document["occurred_at"] == OCCURRED_AT


@pytest.mark.parametrize(
    "raw",
    [
        "Authorization: ******",
        "refresh_token=1//0eXaMpLeToKeNvAlUe",
        "client_secret=sup3rs3cr3tvalue",
        '{"access_token": "ya29.a0AfH6SMB"}',
        "api-key: sk-abcdef1234567890",
    ],
)
def test_sanitize_strips_credential_material(raw: str) -> None:
    sanitized = sanitize_message(raw)
    for needle in (
        "AQXdSP_W41_UPs5ioT_t8HESyODB",
        "1//0eXaMpLeToKeNvAlUe",
        "sup3rs3cr3tvalue",
        "ya29.a0AfH6SMB",
        "sk-abcdef1234567890",
    ):
        assert needle not in sanitized


def test_normalized_message_is_sanitized() -> None:
    document = _normalize(
        ProviderRequestError("HTTP 401 Authorization: ******")
    )
    assert "AQXdSP_secret_token" not in str(document["message"])


def test_retry_policy_honors_retry_after_over_backoff() -> None:
    policy = RetryPolicy(
        max_attempts=3, base_delay_seconds=2, max_delay_seconds=60
    )
    assert policy.delay_before_attempt(attempt=2, retry_after_seconds=17) == 17
    assert policy.delay_before_attempt(attempt=2, retry_after_seconds=None) == 2


def test_retry_policy_caps_backoff() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=2, max_delay_seconds=8)
    assert policy.delay_before_attempt(attempt=5, retry_after_seconds=None) == 8


def test_retry_policy_exhausted() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=4)
    assert policy.should_retry(attempt=2, error=RateLimitedError(retry_after_seconds=1))
    assert not policy.should_retry(
        attempt=3, error=RateLimitedError(retry_after_seconds=1)
    )
    assert not policy.should_retry(attempt=1, error=ProviderRequestError("HTTP 400"))


def test_retry_policy_refuses_unreconciled_unknown_write() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=4)
    timeout = ProviderTimeoutError("external create timed out")
    assert not policy.should_retry(attempt=1, error=timeout, reconciled=False)
    assert policy.should_retry(attempt=1, error=timeout, reconciled=True)
