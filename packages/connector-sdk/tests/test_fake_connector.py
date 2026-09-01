"""RED tests: the Fake Connector honors the full connector protocol.

Dry-run makes zero external calls. Execute is idempotent (duplicate
delivery returns the same object, never a second one). Timeout-after-
create yields UNKNOWN and reconcile finds the object without recreating.
Secrets only flow via SecretResolver; the connector never accepts raw
secret values from the model.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from infra_core.clock import FakeClock
from infra_core.secrets import FakeSecretResolver

from connector_sdk import (
    AuthExpiredError,
    ChannelConnectorConfig,
    ConfigInvalidError,
    FakeConnector,
    FakeHttpClient,
    ProxyPolicy,
    RateLimitedError,
)
from connector_sdk.fake import Fault

from builders import make_config, make_policy, make_proposal


def make_connector(
    *,
    config: ChannelConnectorConfig | None = None,
    http_client: FakeHttpClient | None = None,
    fault: Fault | None = None,
) -> FakeConnector:
    resolver = FakeSecretResolver()
    for ref in (
        "secretref://vault/dmt/dev/linkedin/client-id",
        "secretref://vault/dmt/dev/linkedin/client-secret",
        "secretref://vault/dmt/dev/linkedin/refresh-token",
        "secretref://vault/dmt/dev/egress/proxy-url",
    ):
        resolver._store[ref] = f"synthetic-{ref.rsplit('/', 1)[-1]}"
    return FakeConnector(
        config=config if config is not None else make_config(),
        policy=make_policy(),
        secret_resolver=resolver,
        clock=FakeClock(datetime(2026, 9, 14, tzinfo=timezone.utc)),
        http_client=http_client if http_client is not None else FakeHttpClient(),
        proxy_policy=ProxyPolicy(
            required=True, allowed_fqdns=("api.linkedin.com",)
        ),
        fault=fault,
    )


def test_validate_config_passes_for_mock() -> None:
    connector = make_connector()
    connector.validate_config()


def test_validate_config_rejects_unverified_sandbox() -> None:
    connector = make_connector(config=make_config(mode="sandbox", enabled=True))
    with pytest.raises(ConfigInvalidError):
        connector.validate_config()


def test_health_check_reports_mode_and_no_external_calls() -> None:
    connector = make_connector()
    report = connector.health_check()
    assert report["mode"] == "mock"
    assert connector.external_write_calls == 0


def test_dry_run_makes_zero_external_calls() -> None:
    connector = make_connector()
    result = connector.dry_run(make_proposal().model_dump(mode="json"))
    assert result.valid
    assert connector.external_write_calls == 0
    assert connector.http_client.calls == []  # type: ignore[union-attr]


def test_execute_requires_approval_token_reference() -> None:
    connector = make_connector()
    with pytest.raises(ValueError):
        connector.execute(
            make_proposal().model_dump(mode="json"),
            approval_token_ref="",
            input_hash="sha256:" + "0" * 64,
            idempotency_key="idem-p3-0001",
        )


def test_execute_creates_exactly_once_per_idempotency_key() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    first = connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0001",
    )
    assert first.outcome == "CREATED"
    assert first.external_object_id

    duplicate = connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0001",
    )
    assert duplicate.outcome == "ALREADY_EXISTS"
    assert duplicate.external_object_id == first.external_object_id
    assert connector.external_write_calls == 1


def test_same_key_different_input_hash_rejected() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0001",
    )
    with pytest.raises(ValueError):
        connector.execute(
            request,
            approval_token_ref="approval-token-ref-0001",
            input_hash="sha256:" + "2" * 64,
            idempotency_key="idem-p3-0001",
        )


def test_timeout_after_create_returns_unknown_and_reconcile_finds_object() -> None:
    connector = make_connector(fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
    request = make_proposal().model_dump(mode="json")
    result = connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0002",
    )
    assert result.outcome == "UNKNOWN"
    assert result.external_object_id is None

    reconciled = connector.reconcile(
        request=request, idempotency_key="idem-p3-0002"
    )
    assert reconciled["outcome"] == "RECONCILED"
    assert reconciled["external_object_id"]
    # reconcile never creates a second object
    assert connector.external_write_calls == 1


def test_rate_limit_fault_raises_retryable_with_retry_after() -> None:
    connector = make_connector(fault="HTTP_429")
    with pytest.raises(RateLimitedError) as excinfo:
        connector.execute(
            make_proposal().model_dump(mode="json"),
            approval_token_ref="approval-token-ref-0001",
            input_hash="sha256:" + "1" * 64,
            idempotency_key="idem-p3-0003",
        )
    assert excinfo.value.retry_after_seconds > 0
    assert excinfo.value.retryable is True


def test_auth_expired_fault_not_retryable() -> None:
    connector = make_connector(fault="AUTH_EXPIRED")
    with pytest.raises(AuthExpiredError):
        connector.execute(
            make_proposal().model_dump(mode="json"),
            approval_token_ref="approval-token-ref-0001",
            input_hash="sha256:" + "1" * 64,
            idempotency_key="idem-p3-0004",
        )


def test_get_status_is_reentrant() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    result = connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0005",
    )
    assert result.external_object_id is not None
    for _ in range(3):
        status = connector.get_status(
            external_object_id=result.external_object_id,
            idempotency_key="idem-p3-0005",
        )
        assert status["state"] == "CREATED"
    assert connector.external_write_calls == 1


def test_collect_metrics_returns_deterministic_raw_rows() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    result = connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0006",
    )
    assert result.external_object_id is not None
    rows = connector.collect_metrics(
        account_id="acct-linkedin-dev",
        external_object_id=result.external_object_id,
        window={"start": "2026-09-21T00:00:00Z", "end": "2026-09-22T00:00:00Z"},
    )
    assert rows
    again = connector.collect_metrics(
        account_id="acct-linkedin-dev",
        external_object_id=result.external_object_id,
        window={"start": "2026-09-21T00:00:00Z", "end": "2026-09-22T00:00:00Z"},
    )
    assert rows == again


def test_no_secret_material_in_any_connector_output() -> None:
    connector = make_connector()
    request = make_proposal().model_dump(mode="json")
    outputs: list[str] = [str(connector.health_check())]
    result = connector.execute(
        request,
        approval_token_ref="approval-token-ref-0001",
        input_hash="sha256:" + "1" * 64,
        idempotency_key="idem-p3-0007",
    )
    assert result.external_object_id is not None
    outputs.append(str(result))
    outputs.append(str(connector.dry_run(request).to_document(proposal_id=request["proposal_id"])))
    outputs.append(
        str(
            connector.get_status(
                external_object_id=result.external_object_id,
                idempotency_key="idem-p3-0007",
            )
        )
    )
    for text in outputs:
        assert "synthetic-client-secret" not in text
        assert "synthetic-refresh-token" not in text
        assert "synthetic-proxy-url" not in text


def test_cancel_requires_known_object() -> None:
    connector = make_connector()
    with pytest.raises(ValueError):
        connector.cancel(external_object_id="ext-missing", idempotency_key="idem-x")
