"""Shared builders for connector-sdk tests. Everything is deterministic."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from campaign_draft import CampaignProposalV1, DraftRequest, build_campaign_draft
from content_package import ApprovedContentPackageV1

from connector_sdk import ChannelConnectorConfig, ChannelPolicy

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "content-package"
    / "fixtures"
    / "phase03"
    / "approved-content-package.sample.json"
)

FAKE_NOW = "2026-09-14T00:00:00Z"


def load_package() -> ApprovedContentPackageV1:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return ApprovedContentPackageV1.model_validate(document, strict=False)


def make_proposal(**overrides: Any) -> CampaignProposalV1:
    package = load_package()
    values: dict[str, Any] = {
        "tenant_id": "tenant-cshi",
        "run_id": "run-p3-0002",
        "requester_id": "emp-campaign-op",
        "channel": "linkedin",
        "account_id": "acct-linkedin-dev",
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


def config_document(**overrides: Any) -> dict[str, Any]:
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
        "timeouts": {
            "connect_seconds": 5,
            "read_seconds": 30,
            "total_seconds": 45,
        },
        "proxy": {
            "required": True,
            "url_ref": "secretref://vault/dmt/dev/egress/proxy-url",
            "allow_inbound": False,
        },
        "mock": {
            "deterministic": True,
            "seed": 31014,
        },
    }
    for key, value in overrides.items():
        if value is ...:
            document.pop(key, None)
        else:
            document[key] = value
    return document


def make_config(**overrides: Any) -> ChannelConnectorConfig:
    return ChannelConnectorConfig.model_validate(config_document(**overrides))


def make_policy(**overrides: Any) -> ChannelPolicy:
    values: dict[str, Any] = {
        "policy_version": "campaign-policy-1.0.0",
        "channel": "linkedin",
        "known_accounts": ("acct-linkedin-dev",),
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
