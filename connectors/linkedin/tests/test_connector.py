"""RED tests: LinkedInAdvertisingConnector honors the shared protocol.

Mock/contract only — no real network. Covers dry-run (zero external
calls), execute preconditions (approval token / input hash / idempotency
key), duplicate delivery, 429 with Retry-After, token expiry,
timeout-after-external-create with reconcile-before-retry and partial
hierarchy success (no further writes, created IDs recorded).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from infra_core.clock import FakeClock
from infra_core.secrets import FakeSecretResolver

from connector_sdk import (
    AuthExpiredError,
    ConfigInvalidError,
    RateLimitedError,
)

from linkedin_connector import (
    LinkedInAdvertisingConnector,
    MockLinkedInTransport,
    PartialHierarchyError,
)

from builders import make_config, make_policy, make_proposal


def make_connector(fault: str | None = None) -> LinkedInAdvertisingConnector:
    resolver = FakeSecretResolver()
    for ref, value in (
        ("secretref://vault/dmt/dev/linkedin/client-id", "client-id-public"),
        ("secretref://vault/dmt/dev/linkedin/client-secret", "synthetic-client-secret"),
        ("secretref://vault/dmt/dev/linkedin/refresh-token", "synthetic-refresh-token"),
        ("secretref://vault/dmt/dev/egress/proxy-url", "synthetic-proxy-url"),
    ):
        resolver._store[ref] = value
    return LinkedInAdvertisingConnector(
        config=make_config(),
        policy=make_policy(),
        secret_resolver=resolver,
        clock=FakeClock(datetime(2026, 9, 14, tzinfo=timezone.utc)),
        transport=MockLinkedInTransport(fault=fault),
    )


def execute(connector: LinkedInAdvertisingConnector, key: str, request: dict[str, object]):  # type: ignore[no-untyped-def]
    return connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key=key,
    )


def test_validate_config_mock_ok_sandbox_blocked() -> None:
    connector = make_connector()
    connector.validate_config()
    blocked = LinkedInAdvertisingConnector(
        config=make_config(mode="sandbox", enabled=True),
        policy=make_policy(),
        secret_resolver=FakeSecretResolver(),
        clock=FakeClock(datetime(2026, 9, 14, tzinfo=timezone.utc)),
        transport=MockLinkedInTransport(),
    )
    with pytest.raises(ConfigInvalidError):
        blocked.validate_config()


def test_dry_run_zero_external_calls() -> None:
    connector = make_connector()
    result = connector.dry_run(make_proposal().model_dump(mode="json"))
    assert result.valid
    assert connector.transport.write_calls == 0
    assert connector.transport.read_calls == 0


def test_execute_requires_approval_and_hash_and_key() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    with pytest.raises(ValueError):
        connector.execute(
            request, approval_token_ref="", input_hash="sha256:" + "1" * 64, idempotency_key="k"
        )
    with pytest.raises(ValueError):
        connector.execute(
            request, approval_token_ref="ref", input_hash="not-a-hash", idempotency_key="k"
        )
    with pytest.raises(ValueError):
        connector.execute(
            request, approval_token_ref="ref", input_hash="sha256:" + "1" * 64, idempotency_key=""
        )
    assert connector.transport.write_calls == 0


def test_execute_creates_once_and_duplicate_returns_same_object() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    first = execute(connector, "idem-li-0001", request)
    assert first.outcome == "CREATED"
    assert first.external_object_id is not None
    assert first.external_object_id.startswith("urn:li:sponsoredCampaign:")
    duplicate = execute(connector, "idem-li-0001", request)
    assert duplicate.outcome == "ALREADY_EXISTS"
    assert duplicate.external_object_id == first.external_object_id
    assert connector.transport.write_calls == 1


def test_duplicate_delivery_fault_provider_side() -> None:
    connector = make_connector(fault="DUPLICATE_DELIVERY")
    request = make_proposal().model_dump(mode="json")
    result = execute(connector, "idem-li-0002", request)
    assert result.outcome == "ALREADY_EXISTS"
    assert result.external_object_id is not None


def test_rate_limited_carries_retry_after() -> None:
    connector = make_connector(fault="HTTP_429")
    with pytest.raises(RateLimitedError) as excinfo:
        execute(connector, "idem-li-0003", make_proposal().model_dump(mode="json"))
    assert excinfo.value.retry_after_seconds > 0


def test_auth_expired_not_retryable() -> None:
    connector = make_connector(fault="AUTH_EXPIRED")
    with pytest.raises(AuthExpiredError):
        execute(connector, "idem-li-0004", make_proposal().model_dump(mode="json"))


def test_timeout_after_create_unknown_then_reconcile_no_duplicate() -> None:
    connector = make_connector(fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
    request = make_proposal().model_dump(mode="json")
    result = execute(connector, "idem-li-0005", request)
    assert result.outcome == "UNKNOWN"
    assert result.external_object_id is None
    reconciled = connector.reconcile(request=request, idempotency_key="idem-li-0005")
    assert reconciled["outcome"] == "RECONCILED"
    assert reconciled["external_object_id"]
    assert connector.transport.write_calls == 1
    # after reconcile the duplicate delivery converges without a second write
    again = execute(connector, "idem-li-0005", request)
    assert again.outcome == "ALREADY_EXISTS"
    assert connector.transport.write_calls == 1


def test_partial_hierarchy_stops_and_records_created_ids() -> None:
    connector = make_connector(fault="PARTIAL_HIERARCHY_SUCCESS")
    request = make_proposal().model_dump(mode="json")
    with pytest.raises(PartialHierarchyError) as excinfo:
        execute(connector, "idem-li-0006", request)
    assert excinfo.value.created_object_ids
    document = connector.normalize_error(
        error=excinfo.value,
        trace_id="trace-p3-0006",
        occurred_at="2026-09-14T00:00:00Z",
    )
    assert document["connector"] == "linkedin"
    assert document["retryable"] is False
    assert document["details"]["created_object_ids"] == list(excinfo.value.created_object_ids)


def test_get_status_and_cancel() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    result = execute(connector, "idem-li-0007", request)
    assert result.external_object_id is not None
    status = connector.get_status(
        external_object_id=result.external_object_id, idempotency_key="idem-li-0007"
    )
    assert status["state"] == "DRAFT"
    cancelled = connector.cancel(
        external_object_id=result.external_object_id, idempotency_key="idem-li-0007"
    )
    assert cancelled["state"] == "CANCELLED"


def test_collect_metrics_pages_through_transport() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    result = execute(connector, "idem-li-0008", request)
    assert result.external_object_id is not None
    rows = connector.collect_metrics(
        account_id="acct-linkedin-dev",
        external_object_id=result.external_object_id,
        window={"start": "2026-09-21T00:00:00Z", "end": "2026-09-28T00:00:00Z"},
    )
    assert len(rows) >= 3
    assert all("source_response_hash" in row for row in rows)


def test_no_secret_material_in_outputs() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    result = execute(connector, "idem-li-0009", request)
    assert result.external_object_id is not None
    outputs = [
        str(connector.health_check()),
        str(result),
        str(connector.dry_run(request).to_document(proposal_id=str(request["proposal_id"]))),
        str(
            connector.get_status(
                external_object_id=result.external_object_id, idempotency_key="idem-li-0009"
            )
        ),
    ]
    for text in outputs:
        assert "synthetic-client-secret" not in text
        assert "synthetic-refresh-token" not in text
        assert "synthetic-proxy-url" not in text
