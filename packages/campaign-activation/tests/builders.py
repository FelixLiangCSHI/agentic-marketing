"""Shared deterministic builders for campaign-activation tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from campaign_draft import CampaignProposalV1, DraftRequest, build_campaign_draft
from connector_sdk import ChannelConnectorConfig, ChannelPolicy, FakeConnector
from content_package import ApprovedContentPackageV1
from infra_core.clock import FakeClock
from infra_core.queue import FakeQueueClient, RetryPolicy
from infra_core.secrets import FakeSecretResolver

from campaign_activation import (
    ActivationWorker,
    FakeApprovalConsumer,
    FakeAuditLog,
    FakeCompensationQueue,
    FakeOperationStore,
    FakeOutbox,
    OperationKey,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "content-package"
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)

FAKE_NOW = "2026-09-14T00:00:00Z"
FAKE_DT = datetime(2026, 9, 14, tzinfo=timezone.utc)

TENANT = "tenant-cshi"
CHANNEL = "linkedin"
ACCOUNT = "acct-linkedin-dev"
TOKEN_REF = "approvaltoken://campaign/run-p3-0005/one"


def load_package() -> ApprovedContentPackageV1:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return ApprovedContentPackageV1.model_validate(document, strict=False)


def make_proposal(**overrides: Any) -> CampaignProposalV1:
    package = load_package()
    values: dict[str, Any] = {
        "tenant_id": TENANT,
        "run_id": "run-p3-0005",
        "requester_id": "emp-campaign-op",
        "channel": CHANNEL,
        "account_id": ACCOUNT,
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


def connector_config_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "provider": "linkedin",
        "connector": "connector_sdk.fake.FakeConnector",
        "enabled": False,
        "mode": "mock",
        "endpoint": {
            "base_url": "https://api.linkedin.com",
            "api_version_ref": "env://LINKEDIN_API_VERSION",
            "verify_tls": True,
            "verification": "required-before-sandbox-or-live",
        },
        "auth": {
            "method": "oauth_3legged",
            "client_id_ref": "secretref://vault/dmt/dev/linkedin/client-id",
            "client_secret_ref": "secretref://vault/dmt/dev/linkedin/client-secret",
            "refresh_token_ref": "secretref://vault/dmt/dev/linkedin/refresh-token",
        },
        "rate_limit": {
            "requests_per_window_ref": "config://limits/linkedin/approved-rpm",
            "window_seconds": 60,
        },
        "retry_strategy": {
            "max_attempts": 3,
            "reconcile_before_retry": True,
            "honor_retry_after": True,
            "base_delay_seconds": 2,
            "max_delay_seconds": 60,
        },
        "timeouts": {"connect_seconds": 5, "read_seconds": 30, "total_seconds": 45},
        "proxy": {
            "required": True,
            "url_ref": "secretref://vault/dmt/dev/egress/proxy-url",
            "allow_inbound": False,
        },
        "mock": {"deterministic": True, "seed": 31014},
    }
    document.update(overrides)
    return document


def make_policy(**overrides: Any) -> ChannelPolicy:
    values: dict[str, Any] = {
        "policy_version": "campaign-policy-1.0.0",
        "channel": CHANNEL,
        "known_accounts": (ACCOUNT,),
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


def make_connector(fault: Any = None) -> FakeConnector:
    return FakeConnector(
        config=ChannelConnectorConfig.model_validate(connector_config_document()),
        policy=make_policy(),
        secret_resolver=FakeSecretResolver(),
        clock=FakeClock(FAKE_DT),
        fault=fault,
    )


def make_queue() -> FakeQueueClient:
    return FakeQueueClient(
        clock=FakeClock(FAKE_DT),
        retry_policy=RetryPolicy(
            max_attempts=3, base_delay_seconds=0.0, max_delay_seconds=0.0, jitter_ratio=0.0
        ),
        lease_seconds=300,
    )


def make_key(idempotency_key: str = "idem-act-0001") -> OperationKey:
    return OperationKey(
        tenant_id=TENANT,
        channel=CHANNEL,
        account_id=ACCOUNT,
        idempotency_key=idempotency_key,
    )


class Harness:
    """One fully wired activation worker over deterministic fakes."""

    def __init__(self, *, fault: Any = None) -> None:
        self.clock = FakeClock(FAKE_DT)
        self.queue = make_queue()
        self.store = FakeOperationStore()
        self.approvals = FakeApprovalConsumer()
        self.audit = FakeAuditLog()
        self.outbox = FakeOutbox()
        self.compensations = FakeCompensationQueue()
        self.connector = make_connector(fault)
        self.worker = ActivationWorker(
            queue=self.queue,
            store=self.store,
            approvals=self.approvals,
            audit=self.audit,
            outbox=self.outbox,
            compensations=self.compensations,
            connectors={CHANNEL: self.connector},
            clock=self.clock,
            worker_id="worker-1",
        )

    def enqueue(
        self,
        *,
        idempotency_key: str = "idem-act-0001",
        token_ref: str = TOKEN_REF,
        proposal: CampaignProposalV1 | None = None,
        mint: bool = True,
    ) -> CampaignProposalV1:
        prop = proposal if proposal is not None else make_proposal()
        if mint:
            self.approvals.mint(
                token_ref=token_ref,
                input_hash=prop.input_hash,
                approval_id=f"appr-{idempotency_key}",
            )
        self.queue.enqueue(
            "campaign.activation",
            {
                "tenant_id": TENANT,
                "channel": CHANNEL,
                "account_id": ACCOUNT,
                "approval_token_ref": token_ref,
                "input_hash": prop.input_hash,
                "request": prop.model_dump(mode="json"),
            },
            idempotency_key=idempotency_key,
        )
        return prop
