"""Phase 03 / Subphase 07 — campaign integration quality gate (mock/fakes only).

Integrates the whole Phase 03 stack end to end: approved content package
-> deterministic Campaign Draft -> channel Dry-run -> single-use approval
-> ActivationWorker -> REAL channel connectors (LinkedIn / Google Ads with
their deterministic mock transports) -> reconcile -> raw metrics ingest ->
normalization -> Performance Report -> DRAFT Strategy. No new features;
this suite only exercises what Subphases 01-06 delivered.

Every scenario is deterministic and runs for BOTH channels. Real DEV/SIT
test-account evidence cannot be produced here — those gates stay BLOCKED
and are executed only by the protected pipeline (see
integration/fixtures/phase04_sit/).

Run: pip install -e "packages/harness-core[dev]" -e "packages/infra-core[dev]" \
       -e packages/content-package -e packages/campaign-draft \
       -e packages/connector-sdk -e connectors/linkedin -e connectors/google_ads \
       -e packages/campaign-activation -e "packages/campaign-metrics[dev]"
     python -m pytest integration
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from campaign_activation import (
    ActivationWorker,
    FakeApprovalConsumer,
    FakeAuditLog,
    FakeCompensationQueue,
    FakeOperationStore,
    FakeOutbox,
    OperationKey,
)
from campaign_draft import CampaignProposalV1, DraftRequest, build_campaign_draft
from campaign_metrics import (
    FORMULA_VERSION,
    FakeRawMetricStore,
    FakeWatermarkStore,
    IngestContext,
    MetricsIngestor,
    StrategyEvidenceError,
    build_performance_report,
    build_strategy_recommendation,
    google_ads_fetcher,
    linkedin_fetcher,
    normalize,
)
from connector_sdk import ChannelPolicy
from content_package import ApprovedContentPackageV1
from google_ads_connector import (
    GoogleAdsConnector,
    MockGoogleAdsTransport,
    load_google_ads_config,
)
from google_ads_connector.metrics import fetch_gaql_page
from infra_core.clock import FakeClock
from infra_core.queue import FakeQueueClient, RetryPolicy
from infra_core.secrets import FakeSecretResolver
from linkedin_connector import (
    LinkedInAdvertisingConnector,
    MockLinkedInTransport,
    load_linkedin_config,
)
from linkedin_connector.metrics import fetch_metrics_page

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FIXTURE = (
    REPO_ROOT
    / "packages"
    / "content-package"
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)

FAKE_NOW = "2026-09-14T00:00:00Z"
FAKE_DT = datetime(2026, 9, 14, tzinfo=timezone.utc)
TENANT = "tenant-cshi"
TOPIC = "campaign.activation"
WINDOW = {"start": "2026-09-07", "end": "2026-09-13"}

CHANNELS = ("linkedin", "google_ads")
ACCOUNTS = {"linkedin": "acct-linkedin-dev", "google_ads": "acct-googleads-dev"}
PARTIAL_FAULTS = {
    "linkedin": "PARTIAL_HIERARCHY_SUCCESS",
    "google_ads": "PARTIAL_MUTATE_SUCCESS",
}

# ---------------------------------------------------------------------------
# Deterministic builders (fakes only; no real credentials anywhere).
# ---------------------------------------------------------------------------


def load_package(channel: str) -> ApprovedContentPackageV1:
    document = json.loads(PACKAGE_FIXTURE.read_text(encoding="utf-8"))
    if channel == "google_ads":
        variants = [list(entry) for entry in document["channel_variants"]]
        if not any(name == "google_ads" for name, _ in variants):
            variants.append(["google_ads", ["cv-req-0001"]])
        document["channel_variants"] = variants
    return ApprovedContentPackageV1.model_validate(document, strict=False)


def make_proposal(channel: str, **overrides: Any) -> CampaignProposalV1:
    package = load_package(channel)
    values: dict[str, Any] = {
        "tenant_id": TENANT,
        "run_id": "run-p3-0007",
        "requester_id": "emp-campaign-op",
        "channel": channel,
        "account_id": ACCOUNTS[channel],
        "objective": "LEAD_GENERATION",
        "campaign_name": "alpha-q4-lead-gen",
        "currency": "USD",
        "total_limit": Decimal("1000.00"),
        "daily_limit": Decimal("100.00"),
        "timezone": "America/New_York",
        "start_at": "2026-09-21T00:00:00Z",
        "end_at": "2026-10-02T23:59:59Z",
        "markets": ("US",),
        "excluded_segments": (),
        "policy_version": "campaign-policy-1.0.0",
        "workflow_version": "1.0.0",
    }
    values.update(overrides)
    return build_campaign_draft(
        package=package,
        expected_content_hash=package.content_hash,
        request=DraftRequest(**values),
        as_of=FAKE_NOW,
    )


def make_policy(channel: str, **overrides: Any) -> ChannelPolicy:
    values: dict[str, Any] = {
        "policy_version": "campaign-policy-1.0.0",
        "channel": channel,
        "known_accounts": (ACCOUNTS[channel],),
        "allowed_objectives": ("LEAD_GENERATION", "BRAND_AWARENESS"),
        "allowed_currencies": ("USD", "EUR"),
        "max_total_budget_minor": 500000,
        "max_daily_budget_minor": 50000,
        "allowed_markets": ("US",),
        "max_duration_days": 30,
        "max_campaign_name_length": 100,
    }
    values.update(overrides)
    return ChannelPolicy(**values)


def make_secret_resolver() -> FakeSecretResolver:
    resolver = FakeSecretResolver()
    for ref, value in (
        ("secretref://vault/dmt/dev/linkedin/client-id", "client-id-public"),
        ("secretref://vault/dmt/dev/linkedin/client-secret", "synthetic-client-secret"),
        ("secretref://vault/dmt/dev/linkedin/refresh-token", "synthetic-refresh-token"),
        ("secretref://vault/dmt/dev/egress/proxy-url", "synthetic-proxy-url"),
    ):
        resolver._store[ref] = value
    return resolver


def make_channel_connector(
    channel: str, *, fault: str | None = None, policy: ChannelPolicy | None = None
) -> Any:
    clock = FakeClock(FAKE_DT)
    if channel == "linkedin":
        return LinkedInAdvertisingConnector(
            config=load_linkedin_config(REPO_ROOT / "config" / "linkedin.yaml"),
            policy=policy or make_policy(channel),
            secret_resolver=make_secret_resolver(),
            clock=clock,
            transport=MockLinkedInTransport(fault=fault),
        )
    return GoogleAdsConnector(
        config=load_google_ads_config(REPO_ROOT / "config" / "google_ads.yaml"),
        policy=policy or make_policy(channel),
        secret_resolver=FakeSecretResolver(),
        clock=clock,
        transport=MockGoogleAdsTransport(fault=fault),
    )


class ChannelRig:
    """One fully wired activation pipeline over a REAL channel connector."""

    def __init__(
        self,
        channel: str,
        *,
        fault: str | None = None,
        queue_max_attempts: int = 5,
    ) -> None:
        self.channel = channel
        self.clock = FakeClock(FAKE_DT)
        self.queue = FakeQueueClient(
            clock=self.clock,
            retry_policy=RetryPolicy(
                max_attempts=queue_max_attempts,
                base_delay_seconds=0.0,
                max_delay_seconds=0.0,
                jitter_ratio=0.0,
            ),
            lease_seconds=300,
        )
        self.store = FakeOperationStore()
        self.approvals = FakeApprovalConsumer()
        self.audit = FakeAuditLog()
        self.outbox = FakeOutbox()
        self.compensations = FakeCompensationQueue()
        self.connector = make_channel_connector(channel, fault=fault)
        self.worker = self.make_worker("worker-1")

    def make_worker(self, worker_id: str) -> ActivationWorker:
        return ActivationWorker(
            queue=self.queue,
            store=self.store,
            approvals=self.approvals,
            audit=self.audit,
            outbox=self.outbox,
            compensations=self.compensations,
            connectors={self.channel: self.connector},
            clock=self.clock,
            worker_id=worker_id,
        )

    def key(self, idempotency_key: str = "idem-gate-0001") -> OperationKey:
        return OperationKey(
            tenant_id=TENANT,
            channel=self.channel,
            account_id=ACCOUNTS[self.channel],
            idempotency_key=idempotency_key,
        )

    def enqueue(
        self,
        *,
        idempotency_key: str = "idem-gate-0001",
        proposal: CampaignProposalV1 | None = None,
        mint: bool = True,
    ) -> CampaignProposalV1:
        prop = proposal if proposal is not None else make_proposal(self.channel)
        token_ref = f"approvaltoken://campaign/run-p3-0007/{idempotency_key}"
        if mint:
            self.approvals.mint(
                token_ref=token_ref,
                input_hash=prop.input_hash,
                approval_id=f"appr-{idempotency_key}",
            )
        self.queue.enqueue(
            TOPIC,
            {
                "tenant_id": TENANT,
                "channel": self.channel,
                "account_id": ACCOUNTS[self.channel],
                "approval_token_ref": token_ref,
                "input_hash": prop.input_hash,
                "request": prop.model_dump(mode="json"),
            },
            idempotency_key=idempotency_key,
        )
        return prop

    @property
    def external_objects(self) -> dict[str, dict[str, Any]]:
        return self.connector.transport._objects


def make_metrics_fetcher(channel: str, external_object_id: str) -> Any:
    if channel == "linkedin":
        return linkedin_fetcher(
            config=load_linkedin_config(REPO_ROOT / "config" / "linkedin.yaml"),
            account_id=ACCOUNTS[channel],
            external_object_id=external_object_id,
            window=WINDOW,
            retrieved_at=FAKE_NOW,
            fetch_page=fetch_metrics_page,
        )
    return google_ads_fetcher(
        config=load_google_ads_config(REPO_ROOT / "config" / "google_ads.yaml"),
        customer_id_ref=ACCOUNTS[channel],
        external_object_id=external_object_id,
        window=WINDOW,
        retrieved_at=FAKE_NOW,
        fetch_page=fetch_gaql_page,
    )


def make_ingest_context(channel: str, external_object_id: str) -> IngestContext:
    return IngestContext(
        tenant_id=TENANT,
        channel=channel,
        account_id=ACCOUNTS[channel],
        external_object_id=external_object_id,
        period_start=WINDOW["start"],
        period_end=WINDOW["end"],
        provider_currency="USD",
        provider_timezone="UTC",
        attribution_window="LAST_TOUCH_7D",
        provider_api_version="mock",
        connector_version=f"{channel}-connector-0.1.0",
        trace_id="trace-p3-0007",
        source_response_ref=f"objectstore://local/{TENANT}/metrics/{channel}-raw.json",
    )


def activate(rig: ChannelRig, **kwargs: Any) -> str:
    """Golden-path activation; returns the single external object id."""
    rig.enqueue(**kwargs)
    result = rig.worker.run_once()
    assert result is not None and result.disposition == "ack"
    record = rig.store.get(rig.key(kwargs.get("idempotency_key", "idem-gate-0001")))
    assert record is not None and record.status == "SUCCEEDED"
    assert record.external_object_id is not None
    return record.external_object_id


# ---------------------------------------------------------------------------
# 1. Closed loop: package -> draft -> dry-run -> approval -> publish ->
#    reconcile evidence -> metrics -> normalize -> report -> strategy.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("channel", CHANNELS)
def test_closed_loop_from_approved_package_to_strategy_draft(channel: str) -> None:
    rig = ChannelRig(channel)
    proposal = make_proposal(channel)

    # Draft is deterministic and DRAFT-only.
    assert proposal.status == "DRAFT"
    assert proposal.input_hash == make_proposal(channel).input_hash

    # Dry-run over the real connector: valid, zero external side effects.
    dry = rig.connector.dry_run(proposal.model_dump(mode="json"))
    assert dry.valid is True
    assert rig.connector.transport.write_calls == 0

    # Approval-gated activation through the worker: exactly one object.
    external_id = activate(rig, proposal=proposal)
    assert len(rig.external_objects) == 1
    assert rig.connector.transport.write_calls == 1

    # Status/reconcile evidence is queryable by the recorded external id.
    status = rig.connector.get_status(
        external_object_id=external_id, idempotency_key="idem-gate-0001"
    )
    assert status["external_object_id"] == external_id

    # Raw metrics ingest with the real connector fetch functions.
    raw_store = FakeRawMetricStore()
    ingestor = MetricsIngestor(raw_store=raw_store, watermark_store=FakeWatermarkStore())
    context = make_ingest_context(channel, external_id)
    result = ingestor.run(context=context, fetcher=make_metrics_fetcher(channel, external_id))
    assert result.inserted == 4
    raws = raw_store.records()
    assert all(r.source_response_hash.startswith("sha256:") for r in raws)

    # Normalization never mutates raw and is fully traceable.
    normalized = normalize(tuple(raws), calculated_at=FAKE_NOW)
    assert raw_store.records() == raws
    by_name = {m.canonical_metric: m for m in normalized}
    assert by_name["impressions"].quality_status == "ok"
    for metric in normalized:
        assert metric.formula_version == FORMULA_VERSION
        if metric.quality_status == "ok":
            assert metric.source_raw_metric_ids

    # Performance report: every number traceable, missing stays not_available.
    report = build_performance_report(
        report_id="rpt-" + "a" * 24,
        tenant_id=TENANT,
        run_id="run-p3-0007",
        campaign_id=external_id,
        channel=channel,
        account_id=ACCOUNTS[channel],
        period_start=WINDOW["start"],
        period_end=WINDOW["end"],
        normalized_metrics=normalized,
        approved_budget_minor=proposal.budget.total_limit_minor,
        budget_currency=proposal.budget.currency,
        generated_at=FAKE_NOW,
        trace_id="trace-p3-0007",
    )
    for entry in report["metrics"]:
        if entry["status"] == "ok":
            assert entry["source_raw_metric_ids"]
            assert entry["formula_version"] == FORMULA_VERSION
        else:
            assert entry["value"] is None  # never fabricated, never 0

    # Strategy draft: evidence-bound, DRAFT-only, never executed.
    ok_metrics = [e["canonical_metric"] for e in report["metrics"] if e["status"] == "ok"]
    strategy = build_strategy_recommendation(
        strategy_id="str-" + "b" * 24,
        report=report,
        recommendations=[
            {
                "action_type": "budget_adjustment",
                "summary": "shift budget toward the stronger period",
                "expected_impact": "higher delivery in the approved window",
                "risk": "spend may concentrate in fewer days",
                "confidence": 0.6,
                "evidence_metrics": ok_metrics[:2],
                "next_step": "create_activation_request",
            }
        ],
        generated_at=FAKE_NOW,
    )
    assert strategy["status"] == "DRAFT"
    assert all(rec["executed"] is False for rec in strategy["recommendations"])
    # The strategy step performed no external calls at all.
    assert rig.connector.transport.write_calls == 1


# ---------------------------------------------------------------------------
# 2. Dry-run policy matrix: every violation class blocked before approval.
# ---------------------------------------------------------------------------

DRY_RUN_VIOLATIONS: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...] = (
    ("unknown_account", {"account_id": "acct-unknown"}, {}),
    ("budget_over_cap", {"total_limit": Decimal("9000.00")}, {}),
    ("daily_budget_over_cap", {"daily_limit": Decimal("900.00")}, {}),
    ("disallowed_currency", {"currency": "EUR"}, {"allowed_currencies": ("USD",)}),
    ("disallowed_objective", {"objective": "BRAND_AWARENESS"}, {"allowed_objectives": ("LEAD_GENERATION",)}),
    ("market_violation", {}, {"allowed_markets": ("DE",)}),
    ("schedule_too_long", {}, {"max_duration_days": 5}),
    ("campaign_name_too_long", {}, {"max_campaign_name_length": 10}),
)


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize(
    "name,proposal_overrides,policy_overrides",
    DRY_RUN_VIOLATIONS,
    ids=[v[0] for v in DRY_RUN_VIOLATIONS],
)
def test_dry_run_blocks_violation_with_zero_side_effects(
    channel: str,
    name: str,
    proposal_overrides: dict[str, Any],
    policy_overrides: dict[str, Any],
) -> None:
    connector = make_channel_connector(
        channel, policy=make_policy(channel, **policy_overrides)
    )
    proposal = make_proposal(channel, **proposal_overrides)
    result = connector.dry_run(proposal.model_dump(mode="json"))
    assert result.valid is False
    assert result.errors
    assert connector.transport.write_calls == 0
    assert connector.transport._objects == {}


# ---------------------------------------------------------------------------
# 3. Approval security: invalid tokens never reach the provider.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("channel", CHANNELS)
def test_missing_approval_means_zero_external_writes(channel: str) -> None:
    rig = ChannelRig(channel)
    rig.enqueue(mint=False)
    result = rig.worker.run_once()
    assert result is not None and result.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "FAILED"
    assert rig.connector.transport.write_calls == 0
    assert rig.external_objects == {}


@pytest.mark.parametrize("channel", CHANNELS)
def test_hash_mismatch_invalidates_the_token(channel: str) -> None:
    rig = ChannelRig(channel)
    proposal = make_proposal(channel)
    token_ref = "approvaltoken://campaign/run-p3-0007/idem-gate-0001"
    rig.approvals.mint(
        token_ref=token_ref,
        input_hash="sha256:" + "f" * 64,  # bound to a DIFFERENT input
        approval_id="appr-other",
    )
    rig.queue.enqueue(
        TOPIC,
        {
            "tenant_id": TENANT,
            "channel": channel,
            "account_id": ACCOUNTS[channel],
            "approval_token_ref": token_ref,
            "input_hash": proposal.input_hash,
            "request": proposal.model_dump(mode="json"),
        },
        idempotency_key="idem-gate-0001",
    )
    result = rig.worker.run_once()
    assert result is not None and result.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "FAILED"
    assert rig.connector.transport.write_calls == 0


# ---------------------------------------------------------------------------
# 4. Fault injection and recovery: no duplicates, reconcile before retry.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("channel", CHANNELS)
def test_token_expiry_fails_closed_without_external_object(channel: str) -> None:
    rig = ChannelRig(channel, fault="AUTH_EXPIRED")
    rig.enqueue()
    result = rig.worker.run_once()
    assert result is not None and result.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "FAILED"
    assert rig.external_objects == {}


@pytest.mark.parametrize("channel", CHANNELS)
def test_rate_limit_recovers_with_exactly_one_object(channel: str) -> None:
    rig = ChannelRig(channel, fault="HTTP_429")
    rig.enqueue()
    first = rig.worker.run_once()
    assert first is not None and first.disposition == "retry"
    assert rig.external_objects == {}
    rig.connector.transport.fault = None  # provider window reopens
    second = rig.worker.run_once()
    assert second is not None and second.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "SUCCEEDED"
    assert len(rig.external_objects) == 1


@pytest.mark.parametrize("channel", CHANNELS)
def test_timeout_after_create_reconciles_before_retry(channel: str) -> None:
    rig = ChannelRig(channel, fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
    rig.enqueue()
    first = rig.worker.run_once()
    assert first is not None and first.disposition == "retry"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "UNKNOWN"
    assert len(rig.external_objects) == 1

    second = rig.worker.run_once()  # redelivery: reconcile path, no recreate
    assert second is not None and second.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "RECONCILED"
    assert record.external_object_id in rig.external_objects
    assert len(rig.external_objects) == 1
    assert any(e["event"] == "activation_reconciled" for e in rig.audit.events)


@pytest.mark.parametrize("channel", CHANNELS)
def test_provider_side_duplicate_is_adopted_not_recreated(channel: str) -> None:
    rig = ChannelRig(channel, fault="DUPLICATE_DELIVERY")
    rig.enqueue()
    result = rig.worker.run_once()
    assert result is not None and result.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "SUCCEEDED"
    assert len(rig.external_objects) == 1
    assert rig.connector.transport.write_calls == 0  # adopted, never re-created


@pytest.mark.parametrize("channel", CHANNELS)
def test_hundred_duplicate_deliveries_create_one_object(channel: str) -> None:
    from infra_core.queue import Message

    rig = ChannelRig(channel)
    proposal = rig.enqueue()
    assert rig.worker.run_once() is not None
    ids = set()
    for delivery in range(2, 102):
        outcome = rig.worker.handle(
            Message(
                topic=TOPIC,
                idempotency_key="idem-gate-0001",
                payload={
                    "tenant_id": TENANT,
                    "channel": channel,
                    "account_id": ACCOUNTS[channel],
                    "approval_token_ref": "approvaltoken://campaign/run-p3-0007/idem-gate-0001",
                    "input_hash": proposal.input_hash,
                    "request": proposal.model_dump(mode="json"),
                },
                attempt=1,
                delivery_id=delivery,
            )
        )
        assert outcome.disposition == "ack"
        assert outcome.record is not None
        ids.add(outcome.record.external_object_id)
    assert len(ids) == 1
    assert len(rig.external_objects) == 1
    assert rig.connector.transport.write_calls == 1


@pytest.mark.parametrize("channel", CHANNELS)
def test_worker_restart_dedupes_through_the_ledger(channel: str) -> None:
    rig = ChannelRig(channel)
    rig.enqueue()
    assert rig.worker.run_once() is not None
    from infra_core.queue import Message

    restarted = rig.make_worker("worker-2")  # fresh process, same store/queue
    proposal = make_proposal(channel)
    result = restarted.handle(  # replayed delivery after restart
        Message(
            topic=TOPIC,
            idempotency_key="idem-gate-0001",
            payload={
                "tenant_id": TENANT,
                "channel": channel,
                "account_id": ACCOUNTS[channel],
                "approval_token_ref": "approvaltoken://campaign/run-p3-0007/idem-gate-0001",
                "input_hash": proposal.input_hash,
                "request": proposal.model_dump(mode="json"),
            },
            attempt=2,
            delivery_id=999,
        )
    )
    assert result.disposition == "ack"
    assert rig.connector.transport.write_calls == 1
    assert len(rig.external_objects) == 1


@pytest.mark.parametrize("channel", CHANNELS)
def test_partial_success_stops_writes_and_parks_compensation(channel: str) -> None:
    rig = ChannelRig(channel, fault=PARTIAL_FAULTS[channel])
    rig.enqueue()
    result = rig.worker.run_once()
    assert result is not None and result.disposition == "ack"
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "COMPENSATION_PENDING"
    tasks = rig.compensations.tasks
    assert len(tasks) == 1
    assert tasks[0].created_object_ids  # every created ID recorded
    assert len(rig.external_objects) == 1  # no further writes


@pytest.mark.parametrize("channel", CHANNELS)
def test_undecidable_reconcile_dead_letters_without_second_object(channel: str) -> None:
    rig = ChannelRig(channel, fault="TIMEOUT_AFTER_EXTERNAL_CREATE", queue_max_attempts=3)
    rig.enqueue()
    assert rig.worker.run_once() is not None  # UNKNOWN

    def _raise(**kwargs: Any) -> Any:
        raise RuntimeError("provider lookup unavailable")

    rig.connector.transport.find_campaign = _raise  # type: ignore[method-assign]
    # Also make the connector forget the in-memory ledger hit so reconcile
    # must go to the provider (simulates a worker/process restart).
    rig.connector._ledger.clear()

    while (result := rig.worker.run_once()) is not None:
        assert result.disposition == "retry"
    dead = rig.queue.dlq(TOPIC)
    assert len(dead) == 1  # manual queue, never a second create
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "WAITING_RECONCILIATION"
    assert len(rig.external_objects) == 1


@pytest.mark.parametrize("channel", CHANNELS)
def test_backend_modification_is_reported_not_overwritten(channel: str) -> None:
    rig = ChannelRig(channel)
    external_id = activate(rig)
    # A human edits the object in the provider backend.
    rig.external_objects[external_id]["state"] = "MANUALLY_EDITED"
    status = rig.connector.get_status(
        external_object_id=external_id, idempotency_key="idem-gate-0001"
    )
    assert status["state"] == "MANUALLY_EDITED"  # drift is visible ...
    record = rig.store.get(rig.key())
    assert record is not None and record.status == "SUCCEEDED"  # ... ledger intact
    assert rig.connector.transport.write_calls == 1  # and never auto-"fixed"


# ---------------------------------------------------------------------------
# 5. Metrics / report / strategy evals over the integrated loop.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("channel", CHANNELS)
def test_duplicate_metric_pull_is_idempotent(channel: str) -> None:
    raw_store = FakeRawMetricStore()
    watermarks = FakeWatermarkStore()
    context = make_ingest_context(channel, "ext-fixed")
    fetcher = make_metrics_fetcher(channel, "ext-fixed")
    first = MetricsIngestor(raw_store=raw_store, watermark_store=watermarks).run(
        context=context, fetcher=fetcher
    )
    second = MetricsIngestor(raw_store=raw_store, watermark_store=watermarks).run(
        context=context, fetcher=make_metrics_fetcher(channel, "ext-fixed")
    )
    assert first.inserted == 4
    assert second.inserted == 0
    assert len(raw_store.records()) == 4


@pytest.mark.parametrize("channel", CHANNELS)
def test_missing_provider_values_never_become_zero(channel: str) -> None:
    raw_store = FakeRawMetricStore()
    context = make_ingest_context(channel, "ext-fixed")
    MetricsIngestor(raw_store=raw_store, watermark_store=FakeWatermarkStore()).run(
        context=context, fetcher=make_metrics_fetcher(channel, "ext-fixed")
    )
    normalized = normalize(tuple(raw_store.records()), calculated_at=FAKE_NOW)
    by_name = {m.canonical_metric: m for m in normalized}
    conversions = by_name["conversions"]
    assert conversions.quality_status == "not_available"
    assert conversions.value_decimal is None  # never coerced to 0


def test_strategy_rejects_fabricated_evidence_and_stays_read_only() -> None:
    raw_store = FakeRawMetricStore()
    context = make_ingest_context("linkedin", "ext-fixed")
    MetricsIngestor(raw_store=raw_store, watermark_store=FakeWatermarkStore()).run(
        context=context, fetcher=make_metrics_fetcher("linkedin", "ext-fixed")
    )
    normalized = normalize(tuple(raw_store.records()), calculated_at=FAKE_NOW)
    report = build_performance_report(
        report_id="rpt-" + "c" * 24,
        tenant_id=TENANT,
        run_id="run-p3-0007",
        campaign_id="ext-fixed",
        channel="linkedin",
        account_id=ACCOUNTS["linkedin"],
        period_start=WINDOW["start"],
        period_end=WINDOW["end"],
        normalized_metrics=normalized,
        approved_budget_minor=100000,
        budget_currency="USD",
        generated_at=FAKE_NOW,
        trace_id="trace-p3-0007",
    )
    with pytest.raises(StrategyEvidenceError):
        build_strategy_recommendation(
            strategy_id="str-" + "d" * 24,
            report=report,
            recommendations=[
                {
                    "action_type": "adjust_budget",
                    "summary": "based on a metric that does not exist",
                    "risk": "n/a",
                    "confidence": 0.9,
                    "evidence_metrics": ["fabricated_metric"],
                    "next_step": "new_activation_request",
                }
            ],
            generated_at=FAKE_NOW,
        )


def test_strategy_module_has_no_write_tools() -> None:
    import campaign_metrics.strategy as strategy_module

    source = Path(strategy_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("linkedin_connector", "google_ads_connector", "connector_sdk"):
        assert forbidden not in source
